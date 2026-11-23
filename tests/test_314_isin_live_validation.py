import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.app import create_app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "src" / "templates" / "watch.html"
TEMPLATE = TEMPLATE_PATH.read_text(encoding="utf-8")

VALID_ISIN = "INE3050A0001"
PARTIAL_ISIN = "INE2YB72407"
FIXED_ISIN = "INE2YB724070"
BAD_PATTERN_ISIN = "INE2YB72407X"

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');

function region(start, end) {
  const s = html.indexOf(start);
  if (s === -1) throw new Error('missing marker: ' + start);
  const e = html.indexOf(end, s);
  if (e === -1) throw new Error('missing end marker: ' + end);
  return html.slice(s, e);
}

const valueSrc = region('function isinValue() {', 'function shapeIsValid() {');
const shapeSrc = region('function shapeIsValid() {', 'function serialize() {');
const validationSrc = region(
  'var hint = document.getElementById("c-isin-help");',
  'function writeFactValues(values) {'
);

function makeEl(id) {
  return {
    id: id,
    value: '',
    hidden: false,
    textContent: '',
    disabled: false,
    attrs: {},
    getAttribute: function (name) {
      return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
    },
    setAttribute: function (name, value) { this.attrs[name] = String(value); },
    removeAttribute: function (name) { delete this.attrs[name]; },
    addEventListener: function () {}
  };
}

const isin = makeEl('c-isin');
const hint = makeEl('c-isin-help');
const liveError = makeEl('c-isin-live-error');
const fetchReason = makeEl('c-isin-fetch-reason');
const button = makeEl('c-isin-fetch');
const serverError = makeEl('c-isin-error');
hint.textContent = '12 characters, forced uppercase, unique across the register';
const DEFAULT_HINT = hint.textContent;
isin.attrs = { 'aria-describedby': 'c-isin-help' };

let runFetchCalls = 0;
const context = {
  console: console,
  document: {
    getElementById: function (id) {
      return {
        'c-isin': isin,
        'c-isin-help': hint,
        'c-isin-live-error': liveError,
        'c-isin-fetch-reason': fetchReason,
        'c-isin-fetch': button,
        'c-isin-error': serverError
      }[id] || null;
    }
  },
  isin: isin,
  button: button,
  runFetch: function () { runFetchCalls += 1; }
};
vm.createContext(context);
vm.runInContext(
  valueSrc + '\n' + shapeSrc + '\n' + validationSrc + '\n' +
  'globalThis.api = { onIsinInput: onIsinInput, onIsinBlur: onIsinBlur };',
  context
);
const api = context.api;

function reset(value, serverErrorVisible) {
  isin.value = value;
  isin.attrs = { 'aria-describedby': 'c-isin-help' };
  hint.attrs = {};
  hint.textContent = DEFAULT_HINT;
  hint.hidden = false;
  liveError.attrs = {};
  liveError.textContent = '';
  liveError.hidden = true;
  fetchReason.attrs = {};
  fetchReason.hidden = false;
  fetchReason.textContent = '';
  button.attrs = {};
  button.disabled = false;
  serverError.attrs = {};
  serverError.hidden = !serverErrorVisible;
  runFetchCalls = 0;
}

function snapshot() {
  return {
    hint: hint.textContent,
    hintState: hint.getAttribute('data-state'),
    hintHidden: hint.hidden,
    errorHidden: liveError.hidden,
    errorText: liveError.textContent,
    ariaInvalid: isin.getAttribute('aria-invalid'),
    describedBy: isin.getAttribute('aria-describedby'),
    buttonDisabled: button.disabled,
    reasonHidden: fetchReason.hidden,
    reasonText: fetchReason.textContent,
    serverErrorHidden: serverError.hidden,
    runFetchCalls: runFetchCalls
  };
}

function run(name, steps, serverErrorVisible) {
  reset(steps[0].value, !!serverErrorVisible);
  steps.forEach(function (step) {
    if (step.value !== undefined) isin.value = step.value;
    if (step.action === 'input') api.onIsinInput();
    if (step.action === 'blur') api.onIsinBlur();
  });
  result[name] = snapshot();
}

const result = {};
run('fresh', [{ value: '', action: 'input' }]);
run('partial_typing', [{ value: 'INE2YB72407', action: 'input' }]);
run('partial_blur', [
  { value: 'INE2YB72407', action: 'input' },
  { action: 'blur' }
]);
run('fixed_valid', [
  { value: 'INE2YB72407', action: 'input' },
  { action: 'blur' },
  { value: 'INE2YB724070', action: 'input' }
]);
run('complete_valid', [{ value: 'INE3050A0001', action: 'input' }]);
run('blur_valid', [{ value: 'INE3050A0001', action: 'blur' }]);
run('invalid_pattern_blur', [{ value: 'INE2YB72407X', action: 'blur' }]);
run('invalid_still_invalid', [
  { value: 'INE2YB72407X', action: 'blur' },
  { value: 'INE2YB72407Y', action: 'input' }
]);
run('fixed_from_invalid', [
  { value: 'INE2YB72407X', action: 'blur' },
  { value: 'INE2YB724070', action: 'input' }
]);
run('server_error_cleared', [
  { value: 'INE2YB72407', action: 'blur' },
  { value: 'INE2YB724070', action: 'input' }
], true);

process.stdout.write(JSON.stringify(result));
"""


@pytest.fixture(scope="module")
def states(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node runtime not available for JS behaviour harness")
    workdir = tmp_path_factory.mktemp("isin_314")
    harness = workdir / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(harness), str(TEMPLATE_PATH)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_template_static_contract():
    assert 'id="c-isin-help"' in TEMPLATE
    assert 'id="c-isin-help" hidden' not in TEMPLATE
    assert 'data-isin-hint' in TEMPLATE
    assert 'id="c-isin-live-error"' in TEMPLATE
    assert 'data-isin-live-error' in TEMPLATE
    assert 'id="c-isin-fetch-reason"' in TEMPLATE
    assert 'id="c-isin-fetch"' in TEMPLATE
    assert "isin.addEventListener(\"input\", onIsinInput)" in TEMPLATE
    assert "isin.addEventListener(\"blur\", onIsinBlur)" in TEMPLATE
    assert "button.disabled = !valid" in TEMPLATE
    assert "clearInlineError();" in TEMPLATE
    assert "showInlineError(value, valid);" in TEMPLATE


def test_rendered_field_has_visible_hint_and_gated_button(db_path):
    html = _client(db_path).get("/watch").get_data(as_text=True)
    assert 'id="c-isin-help"' in html
    assert 'id="c-isin-help" hidden' not in html
    assert 'id="c-isin-live-error"' in html
    assert 'id="c-isin-live-error"' in html and 'hidden' in html.split('id="c-isin-live-error"', 1)[1][:120]
    assert 'id="c-isin-fetch-reason"' in html
    assert 'id="c-isin-fetch"' in html


def test_v1_typing_eleven_chars_shows_live_counter_and_disabled_fetch(states):
    state = states["partial_typing"]
    assert state["hint"] == "11/12 characters"
    assert state["hintHidden"] is False
    assert state["hintState"] == "invalid"
    assert state["buttonDisabled"] is True
    assert state["reasonHidden"] is False
    assert "1 more character" in state["reasonText"]
    assert state["errorHidden"] is True
    assert state["ariaInvalid"] is None


def test_v2_blur_eleven_chars_shows_inline_error_with_aria_invalid(states):
    state = states["partial_blur"]
    assert state["errorHidden"] is False
    assert "12 characters" in state["errorText"]
    assert "11/12" in state["errorText"]
    assert state["ariaInvalid"] == "true"
    assert state["describedBy"] == "c-isin-help c-isin-live-error"
    assert state["buttonDisabled"] is True
    assert state["runFetchCalls"] == 0


def test_v3_typing_twelfth_valid_char_clears_error_immediately(states):
    state = states["fixed_valid"]
    assert state["errorHidden"] is True
    assert state["errorText"] == ""
    assert state["ariaInvalid"] is None
    assert state["describedBy"] == "c-isin-help"
    assert "12/12 valid" in state["hint"]
    assert state["buttonDisabled"] is False
    assert state["reasonHidden"] is True


def test_v4_complete_valid_shows_green_hint_and_enables_fetch(states):
    state = states["complete_valid"]
    assert state["hintState"] == "valid"
    assert "12/12 valid" in state["hint"]
    assert state["buttonDisabled"] is False
    assert state["reasonHidden"] is True
    assert state["errorHidden"] is True
    assert states["blur_valid"]["runFetchCalls"] == 1


def test_v5_invalid_twelve_chars_keeps_blur_error_until_fixed(states):
    blurred = states["invalid_pattern_blur"]
    assert blurred["errorHidden"] is False
    assert "format invalid" in blurred["errorText"]
    assert blurred["ariaInvalid"] == "true"
    assert blurred["buttonDisabled"] is True
    assert "valid ISIN format" in blurred["reasonText"]

    still_bad = states["invalid_still_invalid"]
    assert still_bad["errorHidden"] is False
    assert still_bad["buttonDisabled"] is True

    fixed = states["fixed_from_invalid"]
    assert fixed["errorHidden"] is True
    assert fixed["ariaInvalid"] is None
    assert fixed["buttonDisabled"] is False


def test_v6_submit_below_twelve_still_gets_server_400(db_path):
    response = _client(db_path).post(
        "/watch",
        data={
            "company": "Backstop Co",
            "isin": PARTIAL_ISIN,
            "rating": "A",
            "coupon_pct": "8.5",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "ISIN format invalid" in body
    assert 'id="c-isin-error"' in body


def test_state_matrix_decision_table(states):
    expected = {
        "fresh": {"error": False, "disabled": True, "state": "idle"},
        "partial_typing": {"error": False, "disabled": True, "state": "invalid"},
        "partial_blur": {"error": True, "disabled": True, "state": "invalid"},
        "fixed_valid": {"error": False, "disabled": False, "state": "valid"},
        "complete_valid": {"error": False, "disabled": False, "state": "valid"},
        "invalid_pattern_blur": {"error": True, "disabled": True, "state": "invalid"},
        "invalid_still_invalid": {"error": True, "disabled": True, "state": "invalid"},
        "fixed_from_invalid": {"error": False, "disabled": False, "state": "valid"},
    }
    for name, want in expected.items():
        got = states[name]
        assert (not got["errorHidden"]) == want["error"], name
        assert got["buttonDisabled"] == want["disabled"], name
        if name != "fresh":
            assert got["hintState"] == want["state"], name
    assert states["server_error_cleared"]["serverErrorHidden"] is True
    assert states["server_error_cleared"]["buttonDisabled"] is False
