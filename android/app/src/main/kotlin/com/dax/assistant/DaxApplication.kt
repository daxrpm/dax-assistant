package com.dax.assistant

import android.app.Application
import com.dax.assistant.preferences.AppPreferences
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class DaxApplication : Application() {
    @Inject lateinit var preferences: AppPreferences

    override fun onCreate() {
        super.onCreate()
        preferences.applyPersistedLanguage()
    }
}
