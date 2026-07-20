package com.dax.assistant.preferences

import org.junit.Assert.assertEquals
import org.junit.Test

class AppPreferencesTest {
    @Test
    fun unknownStoredValuesFallBackToSafeDefaults() {
        assertEquals(AppLanguage.ENGLISH, AppLanguage.fromStored("unknown"))
        assertEquals(RecognitionMode.ANDROID, RecognitionMode.fromStored("unknown"))
        assertEquals(RecognitionLanguage.AUTO, RecognitionLanguage.fromStored("unknown"))
        assertEquals(SpeechOutputMode.SERVER, SpeechOutputMode.fromStored("unknown"))
        assertEquals(ThemePreference.SYSTEM, ThemePreference.fromStored("unknown"))
    }

    @Test
    fun automaticRecognitionLanguageFollowsAppLanguage() {
        assertEquals("en-US", RecognitionLanguage.AUTO.languageTag(AppLanguage.ENGLISH))
        assertEquals("es-ES", RecognitionLanguage.AUTO.languageTag(AppLanguage.SPANISH))
    }
}
