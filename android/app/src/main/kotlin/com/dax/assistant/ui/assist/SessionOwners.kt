package com.dax.assistant.ui.assist

import android.view.View
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.ViewModelStoreOwner
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.lifecycle.setViewTreeViewModelStoreOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner

/**
 * The owners a `ComposeView` needs when nothing above it is an Activity.
 *
 * `VoiceInteractionSession` is not a `LifecycleOwner`, a `ViewModelStoreOwner`,
 * or a `SavedStateRegistryOwner`, and a `ComposeView` refuses to compose without
 * all three on its view tree. Worse, the failure is quiet in the way that costs
 * an afternoon: the view attaches, no exception reaches logcat, and the overlay
 * simply renders nothing.
 *
 * The lifecycle is driven by hand from the session's own callbacks. Composition
 * only runs between [show] and [hide], so the orb's infinite animations stop
 * when the overlay is not on screen rather than spinning against the battery.
 */
class SessionOwners : LifecycleOwner, ViewModelStoreOwner, SavedStateRegistryOwner {

    private val registry = LifecycleRegistry(this)
    private val savedState = SavedStateRegistryController.create(this)

    override val lifecycle: Lifecycle get() = registry
    override val viewModelStore = ViewModelStore()
    override val savedStateRegistry: SavedStateRegistry get() = savedState.savedStateRegistry

    init {
        // Restore must happen while the lifecycle is still INITIALIZED; moving
        // to CREATED first throws.
        savedState.performAttach()
        savedState.performRestore(null)
    }

    /** Publish the owners onto *view* and bring it to CREATED. */
    fun attach(view: View) {
        view.setViewTreeLifecycleOwner(this)
        view.setViewTreeViewModelStoreOwner(this)
        view.setViewTreeSavedStateRegistryOwner(this)
        registry.currentState = Lifecycle.State.CREATED
    }

    fun show() {
        registry.currentState = Lifecycle.State.RESUMED
    }

    fun hide() {
        // Back to CREATED rather than DESTROYED: the system reuses a session
        // across successive assist gestures, and a destroyed registry cannot be
        // revived.
        if (registry.currentState != Lifecycle.State.DESTROYED) {
            registry.currentState = Lifecycle.State.CREATED
        }
    }

    fun destroy() {
        registry.currentState = Lifecycle.State.DESTROYED
        viewModelStore.clear()
    }
}
