package com.dkbondtracker.app;

import android.app.Activity;
import android.os.Bundle;

/**
 * Placeholder MainActivity.
 * The old WebView UI was removed per issue #337 for from-scratch Flutter rebuild.
 */
public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getFilesDir();
    }
}
