package com.dkbondtracker.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Locale;

public class ExportProvider extends ContentProvider {

    public static final String AUTHORITY = "com.dkbondtracker.app.share";
    public static final String EXPORTS_DIR = "exports";

    @Override
    public boolean onCreate() {
        return true;
    }

    private File exportsRoot() {
        return new File(getContext().getFilesDir(), EXPORTS_DIR);
    }

    private File resolve(Uri uri) {
        String name = uri.getLastPathSegment();
        if (name == null || name.isEmpty()) {
            throw new IllegalArgumentException("missing file name: " + uri);
        }
        File root = exportsRoot();
        File candidate = new File(root, name);
        try {
            String rootPath = root.getCanonicalPath() + File.separator;
            if (!candidate.getCanonicalPath().startsWith(rootPath)) {
                throw new IllegalArgumentException("path escapes exports dir: " + uri);
            }
        } catch (IOException e) {
            throw new IllegalArgumentException("unresolvable path: " + uri);
        }
        return candidate;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        File file = resolve(uri);
        if (!file.isFile()) {
            throw new FileNotFoundException(uri.toString());
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public String getType(Uri uri) {
        String name = uri.getLastPathSegment();
        if (name != null && name.toLowerCase(Locale.ROOT).endsWith(".csv")) {
            return "text/csv";
        }
        return "application/octet-stream";
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("read-only provider");
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read-only provider");
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read-only provider");
    }
}
