package com.swiftra.cliphelper;

import android.app.assist.AssistStructure;
import android.os.CancellationSignal;
import android.service.autofill.AutofillService;
import android.service.autofill.FillCallback;
import android.service.autofill.FillContext;
import android.service.autofill.FillRequest;
import android.service.autofill.SaveCallback;
import android.service.autofill.SaveRequest;
import android.util.Log;

import java.util.List;

/** Logs which package asked this AUTOFILL service to fill; never fills anything. */
public class FillSvc extends AutofillService {
    private static final String TAG = "CLIPHELPER";

    @Override
    public void onFillRequest(FillRequest request, CancellationSignal cancel, FillCallback callback) {
        String pkg = "unknown";
        try {
            List<FillContext> ctx = request.getFillContexts();
            AssistStructure s = ctx.get(ctx.size() - 1).getStructure();
            pkg = s.getActivityComponent().getPackageName();
        } catch (Throwable t) {
            pkg = "error:" + t;
        }
        Log.i(TAG, "AUTOFILL_REQUEST pkg=" + pkg);
        callback.onSuccess(null);
    }

    @Override
    public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        Log.i(TAG, "AUTOFILL_SAVE");
        callback.onSuccess();
    }

    @Override
    public void onConnected() {
        Log.i(TAG, "AUTOFILL_CONNECTED");
    }
}
