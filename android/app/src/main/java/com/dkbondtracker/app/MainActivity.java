package com.dkbondtracker.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.DownloadListener;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class MainActivity extends Activity {

    private static final String TAG = "DKBT";
    private static final int PORT = 5000;
    private static final String EXPORT_DIR = ExportProvider.EXPORTS_DIR;
    private static final Pattern FILENAME = Pattern.compile("filename=\"?([^\";]+)\"?");

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient());
        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition,
                                        String mimeType, long contentLength) {
                startExport(url, contentDisposition, mimeType);
            }
        });
        setContentView(webView);
        webView.loadData("<html><body style='font-family:sans-serif'>DK Bond Tracker starting...</body></html>",
                "text/html", "utf-8");

        final String filesDir = getFilesDir().getAbsolutePath();

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    if (!Python.isStarted()) {
                        Python.start(new com.chaquo.python.android.AndroidPlatform(MainActivity.this));
                    }
                    PyObject launcher = Python.getInstance().getModule("main");
                    PyObject ok = launcher.callAttr("start", filesDir);
                    Log.i(TAG, "python main.start() -> " + ok);
                } catch (Throwable t) {
                    Log.e(TAG, "python start failed", t);
                }
                waitAndLoad();
            }
        }, "dkbt-py-start").start();
    }

    private void startExport(final String url, final String contentDisposition, final String mimeType) {
        if (!isLocal(url)) {
            Log.w(TAG, "ignoring non-local download: " + url);
            return;
        }
        Toast.makeText(this, "Preparing export\u2026", Toast.LENGTH_SHORT).show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    File dir = new File(getFilesDir(), EXPORT_DIR);
                    if (!dir.exists() && !dir.mkdirs()) {
                        throw new IllegalStateException("cannot create export dir");
                    }
                    final String name = exportFileName(url, contentDisposition);
                    File out = new File(dir, name);
                    HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                    conn.setConnectTimeout(5000);
                    conn.setReadTimeout(20000);
                    try (InputStream in = conn.getInputStream();
                         FileOutputStream fos = new FileOutputStream(out)) {
                        byte[] buf = new byte[8192];
                        int n;
                        while ((n = in.read(buf)) > 0) {
                            fos.write(buf, 0, n);
                        }
                    } finally {
                        conn.disconnect();
                    }
                    shareExport(Uri.parse("content://" + ExportProvider.AUTHORITY + "/" + EXPORT_DIR + "/" + name),
                            mimeType);
                } catch (final Exception e) {
                    Log.e(TAG, "export failed", e);
                    new Handler(Looper.getMainLooper()).post(new Runnable() {
                        @Override
                        public void run() {
                            Toast.makeText(MainActivity.this, "Export failed: " + e.getMessage(),
                                    Toast.LENGTH_LONG).show();
                        }
                    });
                }
            }
        }, "dkbt-export").start();
    }

    private void shareExport(final Uri uri, final String mimeType) {
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType((mimeType == null || mimeType.isEmpty()) ? "text/csv" : mimeType);
                send.putExtra(Intent.EXTRA_STREAM, uri);
                send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                Intent chooser = Intent.createChooser(send, "Share export");
                chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivity(chooser);
            }
        });
    }

    private static boolean isLocal(String url) {
        try {
            String host = Uri.parse(url).getHost();
            return "127.0.0.1".equals(host) || "localhost".equals(host);
        } catch (Exception e) {
            return false;
        }
    }

    private static String exportFileName(String url, String contentDisposition) {
        String name = null;
        if (contentDisposition != null) {
            Matcher m = FILENAME.matcher(contentDisposition);
            if (m.find()) {
                name = m.group(1);
            }
        }
        if (name == null || name.isEmpty()) {
            name = Uri.parse(url).getLastPathSegment();
        }
        if (name == null || name.isEmpty()) {
            name = "export.csv";
        }
        return name.replaceAll("[^A-Za-z0-9._-]", "_");
    }

    private void waitAndLoad() {
        for (int i = 0; i < 900; i++) {
            if (ping()) {
                Log.i(TAG, "127.0.0.1:" + PORT + " is up; loading WebView");
                new Handler(Looper.getMainLooper()).post(new Runnable() {
                    @Override
                    public void run() {
                        webView.loadUrl("http://127.0.0.1:" + PORT + "/");
                    }
                });
                return;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                return;
            }
        }
        Log.e(TAG, "server did not come up within timeout");
    }

    private boolean ping() {
        Socket socket = new Socket();
        try {
            socket.connect(new InetSocketAddress("127.0.0.1", PORT), 200);
            socket.close();
            return true;
        } catch (Exception e) {
            try {
                socket.close();
            } catch (Exception ignored) {
            }
            return false;
        }
    }
}
