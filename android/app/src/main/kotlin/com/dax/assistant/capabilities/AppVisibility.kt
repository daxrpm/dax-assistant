package com.dax.assistant.capabilities

import android.app.Activity
import android.app.Application
import android.os.Bundle
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject
import javax.inject.Singleton

/** Process-wide fact used to avoid prohibited background activity launches. */
@Singleton
class AppVisibility @Inject constructor() : Application.ActivityLifecycleCallbacks {
    private val resumedActivities = AtomicInteger(0)

    val isResumed: Boolean
        get() = resumedActivities.get() > 0

    override fun onActivityResumed(activity: Activity) {
        resumedActivities.incrementAndGet()
    }

    override fun onActivityPaused(activity: Activity) {
        resumedActivities.updateAndGet { value -> (value - 1).coerceAtLeast(0) }
    }

    override fun onActivityCreated(activity: Activity, state: Bundle?) = Unit
    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = Unit
    override fun onActivityDestroyed(activity: Activity) = Unit
}
