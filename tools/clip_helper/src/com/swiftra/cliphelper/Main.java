package com.swiftra.cliphelper;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.util.Log;
import android.view.autofill.AutofillManager;
import android.widget.EditText;

/** E2E helper. --es mode set --es text X : put X on the system clipboard. --es mode get : log the clipboard text. */
public class Main extends Activity {
    private static final String TAG = "CLIPHELPER";
    private String mMode = "get";
    private boolean mDone;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        EditText t = new EditText(this);
        setContentView(t);
        String mode = getIntent().getStringExtra("mode");
        if (mode != null) mMode = mode;
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (!hasFocus || mDone) return;
        mDone = true;
        if ("autofill".equals(mMode)) {
            // Positive control: this foreground app asks the selected autofill service to fill its own field.
            EditText f = (EditText) ((android.view.ViewGroup) findViewById(android.R.id.content)).getChildAt(0);
            f.requestFocus();
            AutofillManager am = getSystemService(AutofillManager.class);
            Log.i(TAG, "AUTOFILL_CONTROL enabled=" + (am != null && am.isEnabled()));
            if (am != null) am.requestAutofill(f);
            f.postDelayed(this::finish, 4000);
            return;
        }
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        try {
            if ("set".equals(mMode)) {
                String text = getIntent().getStringExtra("text");
                cm.setPrimaryClip(ClipData.newPlainText("e2e", text == null ? "" : text));
                Log.i(TAG, "SET_OK");
            } else {
                ClipData d = cm.getPrimaryClip();
                if (d == null || d.getItemCount() == 0) {
                    Log.i(TAG, "GET none");
                } else {
                    CharSequence s = d.getItemAt(0).coerceToText(this);
                    Log.i(TAG, "GET text=[" + (s == null ? "" : s.toString()) + "]");
                }
            }
        } catch (Throwable e) {
            Log.i(TAG, "ERR " + e);
        }
        finish();
    }
}
