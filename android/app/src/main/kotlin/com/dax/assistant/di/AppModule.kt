package com.dax.assistant.di

import android.content.Context
import com.dax.assistant.diagnostics.CapabilityProbe
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class IoDispatcher

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    /**
     * Injected rather than referenced directly so tests can substitute a test
     * dispatcher; the probe does blocking audio work and must never land on
     * the main thread.
     */
    @Provides
    @IoDispatcher
    fun provideIoDispatcher(): CoroutineDispatcher = Dispatchers.IO

    @Provides
    @Singleton
    fun provideCapabilityProbe(
        @ApplicationContext context: Context,
        @IoDispatcher io: CoroutineDispatcher,
    ): CapabilityProbe = CapabilityProbe(context, io)
}
