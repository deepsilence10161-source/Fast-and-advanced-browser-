package org.chromium.build.annotations;
import java.lang.annotation.ElementType;
import java.lang.annotation.Target;
/** Test-only stub of the Chromium annotation (real one lives in //build/android). */
@Target({ElementType.TYPE_USE, ElementType.METHOD, ElementType.FIELD, ElementType.PARAMETER, ElementType.LOCAL_VARIABLE})
public @interface Nullable {}
