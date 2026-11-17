package androidx.preference;
public class Preference {
    public interface OnPreferenceChangeListener { boolean onPreferenceChange(Preference preference, Object newValue); }
    public void setOnPreferenceChangeListener(OnPreferenceChangeListener l) {}
}
