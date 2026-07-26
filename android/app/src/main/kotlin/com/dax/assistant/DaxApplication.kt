package com.dax.assistant

import android.app.Application
import com.dax.assistant.preferences.AppPreferences
import com.dax.assistant.capabilities.AppVisibility
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class DaxApplication : Application() {
    @Inject lateinit var preferences: AppPreferences
    @Inject lateinit var appVisibility: AppVisibility

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(appVisibility)
        preferences.applyPersistedLanguage()
    }
}
