(function () {
  function closeTips(except) {
    document.querySelectorAll(".tip-wrap.tip-open").forEach(function (wrap) {
      if (wrap !== except) {
        wrap.classList.remove("tip-open");
      }
    });
  }
  document.querySelectorAll(".tip-trigger").forEach(function (trigger) {
    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      var wrap = trigger.closest ? trigger.closest(".tip-wrap") : null;
      if (!wrap) {
        return;
      }
      var open = wrap.classList.toggle("tip-open");
      closeTips(open ? wrap : null);
    });
  });
  document.addEventListener("click", function () {
    closeTips(null);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    closeTips(null);
    var active = document.activeElement;
    if (active && active.classList && active.classList.contains("tip-trigger")) {
      active.blur();
    }
  });
})();

(function () {
  function panelToggle(buttonId, panelId, closeId) {
    var button = document.getElementById(buttonId);
    var panel = document.getElementById(panelId);
    var close = document.getElementById(closeId);
    if (!panel) {
      return null;
    }
    function setOpen(open) {
      panel.hidden = !open;
      if (button) {
        button.setAttribute("aria-expanded", open ? "true" : "false");
      }
    }
    if (button) {
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        setOpen(panel.hidden);
      });
    }
    if (close) {
      close.addEventListener("click", function () {
        setOpen(false);
      });
    }
    return setOpen;
  }
  var closeGuide = panelToggle("guideBtn", "pageGuide", "guideClose");
  var closeWhy = panelToggle("whyBondsBtn", "whyBonds", "whyClose");
  document.addEventListener("click", function (event) {
    var guide = document.getElementById("pageGuide");
    var why = document.getElementById("whyBonds");
    if (guide && !guide.hidden && event.target === guide && closeGuide) {
      closeGuide(false);
    }
    if (why && !why.hidden && event.target === why && closeWhy) {
      closeWhy(false);
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    if (closeGuide) {
      closeGuide(false);
    }
    if (closeWhy) {
      closeWhy(false);
    }
  });
})();

(function () {
  var wrap = document.getElementById("searchWrap");
  var button = document.getElementById("searchBtn");
  var panel = document.getElementById("searchPanel");
  var input = document.getElementById("searchInput");
  var list = document.getElementById("searchResults");
  if (!wrap || !button || !panel || !input || !list) {
    return;
  }
  var options = [];
  var activeIndex = -1;
  function setExpanded(open) {
    button.setAttribute("aria-expanded", open ? "true" : "false");
    input.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function closeList() {
    list.hidden = true;
    list.innerHTML = "";
    options = [];
    activeIndex = -1;
    input.removeAttribute("aria-activedescendant");
    setExpanded(false);
  }
  function closePanel() {
    panel.hidden = true;
    closeList();
  }
  function openPanel() {
    panel.hidden = false;
    input.focus();
  }
  function highlight(index) {
    options.forEach(function (option) {
      option.classList.remove("active");
      option.setAttribute("aria-selected", "false");
    });
    if (index < 0 || index >= options.length) {
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    activeIndex = index;
    options[index].classList.add("active");
    options[index].setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", options[index].id);
  }
  function render(groups) {
    list.innerHTML = "";
    options = [];
    var count = 0;
    groups.forEach(function (group) {
      group.hits.forEach(function (hit) {
        var item = document.createElement("li");
        item.className = "search-option";
        item.id = "search-option-" + count;
        item.setAttribute("role", "option");
        item.setAttribute("data-href", hit.href);
        item.textContent = hit.company + " \u00b7 " + hit.isin + " \u00b7 " + hit.chip;
        item.addEventListener("mousedown", function (event) {
          event.preventDefault();
          window.location.href = hit.href;
        });
        list.appendChild(item);
        options.push(item);
        count += 1;
      });
    });
    if (count === 0) {
      var empty = document.createElement("li");
      empty.className = "search-empty";
      empty.id = "search-live-empty";
      empty.textContent = "No matches for that search.";
      list.appendChild(empty);
      list.hidden = false;
      setExpanded(true);
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    list.hidden = false;
    setExpanded(true);
    highlight(-1);
  }
  function runSearch() {
    var query = input.value.trim();
    if (!query) {
      closeList();
      return;
    }
    fetch("/search?format=json&q=" + encodeURIComponent(query), { credentials: "same-origin" })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        render(data.groups || []);
      })
      .catch(function () {
        closeList();
      });
  }
  button.addEventListener("click", function (event) {
    event.stopPropagation();
    if (panel.hidden) {
      openPanel();
    } else {
      closePanel();
    }
  });
  input.addEventListener("input", runSearch);
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      highlight(Math.min(activeIndex + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlight(Math.max(activeIndex - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && options[activeIndex]) {
        window.location.href = options[activeIndex].getAttribute("data-href");
      } else if (input.value.trim()) {
        window.location.href = "/search?q=" + encodeURIComponent(input.value.trim());
      }
    } else if (event.key === "Escape") {
      closeList();
    }
  });
  document.addEventListener("click", function (event) {
    if (!wrap.contains(event.target)) {
      closePanel();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closePanel();
      return;
    }
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return;
    }
    if (event.key === "/" || (event.key === "k" && (event.metaKey || event.ctrlKey))) {
      event.preventDefault();
      openPanel();
    }
  });
})();
