package com.dkbondtracker.spike;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.net.InetSocketAddress;
import java.net.Socket;

public class MainActivity extends Activity {

    private static final String TAG = "DKBTSPIKE-B";
    private static final int PORT = 5000;

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient());
        setContentView(webView);
        webView.loadData("<html><body style='font-family:sans-serif'>DKBTSPIKE-B starting...</body></html>",
                "text/html", "utf-8");

        final String filesDir = getFilesDir().getAbsolutePath();

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    if (!Python.isStarted()) {
                        Python.start(new com.chaquo.python.android.AndroidPlatform(MainActivity.this));
                    }
                    PyObject server = Python.getInstance().getModule("server");
                    PyObject ok = server.callAttr("start", filesDir);
                    Log.i(TAG, "python server.start() -> " + ok);
                } catch (Throwable t) {
                    Log.e(TAG, "python start failed", t);
                }
                waitAndLoad();
            }
        }, "dkbt-py-start").start();
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
