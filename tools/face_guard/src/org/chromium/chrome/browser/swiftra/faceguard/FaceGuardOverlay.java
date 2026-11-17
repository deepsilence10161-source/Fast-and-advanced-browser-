package org.chromium.chrome.browser.swiftra.faceguard;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Opaque full-window lock screen shown over the browser while Face Guard is locked. Built in code (no resources). */
final class FaceGuardOverlay extends FrameLayout {
    interface Actions {
        void onUnlockWithDeviceCredential();

        void onGrantCamera();

        void onOpenAppSettings();

        void onTurnOff();
    }

    private final TextView mMessage;
    private final Button mCredential;
    private final Button mGrant;
    private final Button mAppSettings;
    private final Button mTurnOff;

    FaceGuardOverlay(Context context, Actions actions) {
        super(context);
        setBackgroundColor(0xFF10151A);       // fully opaque: tab thumbnails/titles underneath are never visible
        setClickable(true);                   // swallow every touch
        setFocusable(true);
        setOnTouchListener((v, e) -> true);

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER_HORIZONTAL);
        int pad = dp(24);
        column.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(context);
        title.setText("Face Guard");
        title.setTextColor(Color.WHITE);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        column.addView(title);

        mMessage = new TextView(context);
        mMessage.setTextColor(0xFFC9D1D9);
        mMessage.setTextSize(16);
        mMessage.setGravity(Gravity.CENTER);
        mMessage.setPadding(0, dp(12), 0, dp(20));
        column.addView(mMessage);

        mCredential = button(context, "Unlock with device PIN", actions::onUnlockWithDeviceCredential);
        mGrant = button(context, "Allow camera", actions::onGrantCamera);
        mAppSettings = button(context, "Open app settings", actions::onOpenAppSettings);
        mTurnOff = button(context, "Turn off Face Guard", actions::onTurnOff);
        column.addView(mCredential);
        column.addView(mGrant);
        column.addView(mAppSettings);
        column.addView(mTurnOff);

        LayoutParams lp = new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        addView(column, lp);
    }

    private Button button(Context context, String text, Runnable action) {
        Button b = new Button(context);
        b.setText(text);
        b.setAllCaps(false);
        b.setOnClickListener(v -> action.run());
        b.setVisibility(View.GONE);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    /** Messages never include page, tab, account or face data. */
    void show(FaceGuardPolicy.Reason reason, boolean hasDeviceCredential) {
        String msg;
        boolean grant = false;
        switch (reason) {
            case PERMISSION_DENIED:
                msg = "Camera permission is needed. Face Guard stays locked until a face is visible to the front camera.";
                grant = true;
                break;
            case CAMERA_UNAVAILABLE:
                msg = "The front camera is not available, so Face Guard stays locked.";
                break;
            case OTHER_FACE:
                msg = "More than one face is visible. Only one person may look at the browser.";
                break;
            case BACKGROUND:
            case WAITING_FOR_OWNER:
            case OWNER_ABSENT:
            case NO_FRAMES:
            default:
                msg = "Looking for your face\u2026 The tab switcher is open behind this screen.";
                break;
        }
        mMessage.setText(msg + "\n\nThis build checks that a face is present. It does not recognise whose face it is.");
        mCredential.setVisibility(hasDeviceCredential ? View.VISIBLE : View.GONE);
        mGrant.setVisibility(grant ? View.VISIBLE : View.GONE);
        mAppSettings.setVisibility(grant ? View.VISIBLE : View.GONE);
        // Without a device credential there is no stronger way to prove ownership, so never lock the user out.
        mTurnOff.setVisibility(hasDeviceCredential ? View.GONE : View.VISIBLE);
    }
}
