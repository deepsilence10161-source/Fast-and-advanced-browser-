package com.swiftra.cliphelper;

import android.credentials.GetCredentialException;
import android.credentials.CreateCredentialException;
import android.os.CancellationSignal;
import android.os.OutcomeReceiver;
import android.service.credentials.BeginCreateCredentialRequest;
import android.service.credentials.BeginCreateCredentialResponse;
import android.service.credentials.BeginGetCredentialRequest;
import android.service.credentials.BeginGetCredentialResponse;
import android.service.credentials.CallingAppInfo;
import android.service.credentials.ClearCredentialStateRequest;
import android.service.credentials.CredentialProviderService;
import android.util.Log;

/** CI observer: logs which package asks the system credential provider (passkeys/passwords); returns nothing. */
public class CredSvc extends CredentialProviderService {
    private static final String TAG = "CLIPHELPER";

    private static String who(CallingAppInfo info) {
        return info == null ? "unknown" : info.getPackageName();
    }

    @Override
    public void onBeginGetCredential(BeginGetCredentialRequest request, CancellationSignal cancel,
            OutcomeReceiver<BeginGetCredentialResponse, GetCredentialException> callback) {
        Log.i(TAG, "CRED_GET pkg=" + who(request.getCallingAppInfo()));
        callback.onResult(new BeginGetCredentialResponse.Builder().build());
    }

    @Override
    public void onBeginCreateCredential(BeginCreateCredentialRequest request, CancellationSignal cancel,
            OutcomeReceiver<BeginCreateCredentialResponse, CreateCredentialException> callback) {
        Log.i(TAG, "CRED_CREATE pkg=" + who(request.getCallingAppInfo()));
        callback.onError(new CreateCredentialException(CreateCredentialException.TYPE_NO_CREATE_OPTIONS));
    }

    @Override
    public void onClearCredentialState(ClearCredentialStateRequest request, CancellationSignal cancel,
            OutcomeReceiver<Void, android.credentials.ClearCredentialStateException> callback) {
        Log.i(TAG, "CRED_CLEAR pkg=" + who(request.getCallingAppInfo()));
        callback.onResult(null);
    }
}
