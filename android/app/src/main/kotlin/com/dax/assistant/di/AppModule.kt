package com.dax.assistant.di

import android.content.Context
import com.dax.assistant.assistant.AssistantController
import com.dax.assistant.audio.AudioRouteManager
import com.dax.assistant.audio.Speaker
import com.dax.assistant.audio.SpeechRecognition
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.diagnostics.CapabilityProbe
import com.dax.assistant.trigger.MediaButtonTrigger
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import java.util.concurrent.TimeUnit
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import okhttp3.OkHttpClient

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class IoDispatcher

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class AppScope

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @IoDispatcher
    fun provideIoDispatcher(): CoroutineDispatcher = Dispatchers.IO

    /**
     * Outlives any screen.
     *
     * The socket and the assistant turn must survive the activity being
     * destroyed — a turn started from a locked screen has no activity at all —
     * so they run on an application-lifetime scope. SupervisorJob keeps one
     * failed turn from cancelling the socket.
     */
    @Provides
    @Singleton
    @AppScope
    fun provideAppScope(): CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Provides
    @Singleton
    fun provideHttpClient(): OkHttpClient = OkHttpClient.Builder()
        // Long read timeout: a WebSocket is mostly idle, and a short one would
        // tear down a healthy connection between turns.
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .connectTimeout(15, TimeUnit.SECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        // Cleartext is permitted only because the backend is commonly reached
        // over a private network or VPN; the settings screen warns when a
        // non-loopback URL is not HTTPS.
        .retryOnConnectionFailure(true)
        .build()

    @Provides
    @Singleton
    fun provideCredentialStore(@ApplicationContext context: Context): CredentialStore =
        CredentialStore(context)

    @Provides
    @Singleton
    fun provideBackendAuth(client: OkHttpClient, credentials: CredentialStore): BackendAuth =
        BackendAuth(client, credentials)

    @Provides
    @Singleton
    fun provideChatSocket(
        client: OkHttpClient,
        credentials: CredentialStore,
        auth: BackendAuth,
        @AppScope scope: CoroutineScope,
    ): ChatSocket = ChatSocket(client, credentials, auth, scope)

    @Provides
    @Singleton
    fun provideAudioRouteManager(@ApplicationContext context: Context): AudioRouteManager =
        AudioRouteManager(context)

    @Provides
    @Singleton
    fun provideSpeechRecognition(@ApplicationContext context: Context): SpeechRecognition =
        SpeechRecognition(context)

    @Provides
    @Singleton
    fun provideSpeaker(@ApplicationContext context: Context): Speaker = Speaker(context)

    @Provides
    @Singleton
    fun provideMediaButtonTrigger(@ApplicationContext context: Context): MediaButtonTrigger =
        MediaButtonTrigger(context)

    @Provides
    @Singleton
    fun provideAssistantController(
        socket: ChatSocket,
        routes: AudioRouteManager,
        recognition: SpeechRecognition,
        speaker: Speaker,
        @AppScope scope: CoroutineScope,
    ): AssistantController = AssistantController(socket, routes, recognition, speaker, scope)

    @Provides
    @Singleton
    fun provideCapabilityProbe(
        @ApplicationContext context: Context,
        @IoDispatcher io: CoroutineDispatcher,
    ): CapabilityProbe = CapabilityProbe(context, io)
}
