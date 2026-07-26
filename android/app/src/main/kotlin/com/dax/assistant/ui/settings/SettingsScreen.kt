package com.dax.assistant.ui.settings

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Troubleshoot
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.activity.compose.rememberLauncherForActivityResult
import com.dax.assistant.R
import com.dax.assistant.data.transport.CapabilityConnectionState
import com.dax.assistant.mobileapi.MobileConfig
import com.dax.assistant.preferences.AppLanguage
import com.dax.assistant.preferences.RecognitionLanguage
import com.dax.assistant.preferences.RecognitionMode
import com.dax.assistant.preferences.SpeechOutputMode
import com.dax.assistant.preferences.ThemePreference
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.design.OrbitaType
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

private enum class SettingsSection { INTERFACE, INTELLIGENCE, NODES, SPEECH }

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    onLoad: () -> Unit,
    onUpdate: ((MobileConfig) -> MobileConfig) -> Unit,
    onSave: () -> Unit,
    onAppLanguageChange: (AppLanguage) -> Unit,
    onRecognitionModeChange: (RecognitionMode) -> Unit,
    onRecognitionLanguageChange: (RecognitionLanguage) -> Unit,
    onSpeechOutputModeChange: (SpeechOutputMode) -> Unit,
    onFollowUpChange: (Boolean) -> Unit,
    onSpeakChatChange: (Boolean) -> Unit,
    onThemeChange: (ThemePreference) -> Unit,
    onNodeCodeChange: (String) -> Unit,
    onNodeQr: (String) -> Unit,
    onEnrolNode: () -> Unit,
    onNodeEnabledChange: (Boolean) -> Unit,
    onForgetNode: () -> Unit,
    onNodePermissionsChanged: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    modifier: Modifier = Modifier,
) {
    androidx.compose.runtime.LaunchedEffect(Unit) { if (!state.loaded) onLoad() }
    var expanded by remember { mutableStateOf<SettingsSection?>(null) }
    var advanced by remember { mutableStateOf(false) }
    val nodeScanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let(onNodeQr)
    }
    val notificationAccessLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { onNodePermissionsChanged() }
    val callPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { onNodePermissionsChanged() }
    val appSettingsLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { onNodePermissionsChanged() }
    val context = LocalContext.current
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { onNodePermissionsChanged() }

    Box(modifier.fillMaxSize().background(Orbita.colors.bgWindow)) {
    Column(
        Modifier.fillMaxSize().widthIn(max = 760.dp).align(Alignment.TopCenter)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x6),
    ) {
        Text(
            stringResource(R.string.settings_title),
            style = OrbitaType.largeTitle,
            color = Orbita.colors.fgPrimary,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            stringResource(R.string.settings_intro),
            style = OrbitaType.callout,
            color = Orbita.colors.fgTertiary,
        )
        Spacer(Modifier.height(Orbita.spacing.x6))

        if (state.loading) {
            CircularProgressIndicator(
                color = Orbita.colors.accent,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            )
        } else {
            SettingsCard(
                title = stringResource(R.string.settings_interface),
                summary = stringResource(
                    R.string.settings_interface_summary,
                    languageLabel(state.preferences.appLanguage),
                    themeLabel(state.preferences.theme),
                ),
                expanded = expanded == SettingsSection.INTERFACE,
                onToggle = {
                    expanded = SettingsSection.INTERFACE.takeUnless { expanded == it }
                    advanced = false
                },
            ) {
                SettingBlock(
                    title = stringResource(R.string.settings_app_language),
                    description = stringResource(R.string.settings_app_language_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            AppLanguage.ENGLISH to stringResource(R.string.language_english),
                            AppLanguage.SPANISH to stringResource(R.string.language_spanish),
                        ),
                        selected = state.preferences.appLanguage,
                        onSelect = onAppLanguageChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_theme),
                    description = stringResource(R.string.settings_theme_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            ThemePreference.SYSTEM to stringResource(R.string.theme_system),
                            ThemePreference.DARK to stringResource(R.string.theme_dark),
                            ThemePreference.LIGHT to stringResource(R.string.theme_light),
                        ),
                        selected = state.preferences.theme,
                        recommended = ThemePreference.SYSTEM,
                        onSelect = onThemeChange,
                    )
                }
            }

            Spacer(Modifier.height(Orbita.spacing.x3))
            SettingsCard(
                title = stringResource(R.string.settings_intelligence),
                summary = state.config.provider.ifBlank { stringResource(R.string.settings_not_configured) },
                expanded = expanded == SettingsSection.INTELLIGENCE,
                onToggle = {
                    expanded = SettingsSection.INTELLIGENCE.takeUnless { expanded == it }
                    advanced = false
                },
            ) {
                SettingBlock(
                    title = stringResource(R.string.settings_provider),
                    description = stringResource(R.string.settings_provider_help),
                ) {
                    val providers = choices(listOf("ollama", "anthropic", "openai"), state.config.provider)
                    ChoiceRow(
                        options = providers.map { it to it.providerName() },
                        selected = state.config.provider,
                        recommended = "ollama",
                    ) { value -> onUpdate { it.copy(provider = value) } }
                }
                ProviderStatus(state.config.provider, state.config.providerConfigured)
                AdvancedDisclosure(expanded = advanced, onToggle = { advanced = !advanced }) {
                    ModelField(
                        label = stringResource(R.string.settings_primary_model),
                        value = state.config.models[state.config.provider].orEmpty(),
                    ) { value ->
                        onUpdate { config -> config.copy(models = config.models + (config.provider to value)) }
                    }
                    SettingBlock(
                        title = stringResource(R.string.settings_fallback),
                        description = stringResource(R.string.settings_fallback_help),
                    ) {
                        val fallbackChoices = choices(
                            listOf("ollama", "anthropic", "openai", "gemini", "deepseek", "codex"),
                            state.config.fallbackOrder,
                        )
                        MultiChoiceRow(
                            options = fallbackChoices,
                            selected = state.config.fallbackOrder,
                        ) { provider ->
                            onUpdate { config ->
                                val next = if (provider in config.fallbackOrder) {
                                    config.fallbackOrder - provider
                                } else {
                                    config.fallbackOrder + provider
                                }
                                config.copy(fallbackOrder = next.filterNot { it == config.provider })
                            }
                        }
                    }
                    state.config.fallbackOrder.filterNot { it == state.config.provider }.forEach { provider ->
                        ModelField(
                            label = stringResource(R.string.settings_model_for, provider),
                            value = state.config.models[provider].orEmpty(),
                        ) { value ->
                            onUpdate { config -> config.copy(models = config.models + (provider to value)) }
                        }
                    }
                }
            }

            Spacer(Modifier.height(Orbita.spacing.x3))
            SettingsCard(
                title = stringResource(R.string.settings_nodes),
                summary = nodeSummary(state.config),
                expanded = expanded == SettingsSection.NODES,
                onToggle = {
                    expanded = SettingsSection.NODES.takeUnless { expanded == it }
                    advanced = false
                },
            ) {
                PhoneCapabilityNode(
                    state = state,
                    onCodeChange = onNodeCodeChange,
                    onScan = {
                        nodeScanner.launch(
                            ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                                .setBeepEnabled(false).setOrientationLocked(false),
                        )
                    },
                    onEnrol = onEnrolNode,
                    onEnabledChange = onNodeEnabledChange,
                    onForget = onForgetNode,
                    onNotificationAccess = {
                        notificationAccessLauncher.launch(
                            Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS),
                        )
                    },
                    onCallPermission = {
                        if (state.callPermission) {
                            appSettingsLauncher.launch(
                                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                                    .setData(Uri.fromParts("package", context.packageName, null)),
                            )
                        } else {
                            callPermissionLauncher.launch(Manifest.permission.CALL_PHONE)
                        }
                    },
                )
                NodePresence(state.config)
                SettingBlock(
                    title = stringResource(R.string.settings_nodes_prefer),
                    description = stringResource(R.string.settings_nodes_prefer_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            true to stringResource(R.string.choice_on),
                            false to stringResource(R.string.choice_off),
                        ),
                        selected = state.config.nodesPreferWhenAvailable,
                        recommended = true,
                    ) { value -> onUpdate { it.copy(nodesPreferWhenAvailable = value) } }
                }
                SettingBlock(
                    title = stringResource(R.string.settings_nodes_enabled),
                    description = stringResource(R.string.settings_nodes_enabled_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            true to stringResource(R.string.choice_on),
                            false to stringResource(R.string.choice_off),
                        ),
                        selected = state.config.nodesEnabled,
                        recommended = true,
                    ) { value -> onUpdate { it.copy(nodesEnabled = value) } }
                }
            }

            Spacer(Modifier.height(Orbita.spacing.x3))
            SettingsCard(
                title = stringResource(R.string.settings_speech),
                summary = recognitionSummary(state),
                expanded = expanded == SettingsSection.SPEECH,
                onToggle = {
                    expanded = SettingsSection.SPEECH.takeUnless { expanded == it }
                    advanced = false
                },
            ) {
                SettingBlock(
                    title = stringResource(R.string.settings_recognition_mode),
                    description = stringResource(R.string.settings_recognition_mode_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            RecognitionMode.ANDROID to stringResource(R.string.recognition_android),
                            RecognitionMode.SERVER to stringResource(R.string.recognition_server),
                        ),
                        selected = state.preferences.recognitionMode,
                        recommended = RecognitionMode.ANDROID,
                        onSelect = onRecognitionModeChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_speech_output),
                    description = stringResource(R.string.settings_speech_output_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            SpeechOutputMode.SERVER to stringResource(R.string.speech_output_server),
                            SpeechOutputMode.ANDROID to stringResource(R.string.speech_output_android),
                        ),
                        selected = state.preferences.speechOutputMode,
                        recommended = SpeechOutputMode.SERVER,
                        onSelect = onSpeechOutputModeChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_recognition_language),
                    description = stringResource(R.string.settings_recognition_language_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            RecognitionLanguage.AUTO to stringResource(R.string.recognition_auto),
                            RecognitionLanguage.ENGLISH_US to "en-US",
                            RecognitionLanguage.SPANISH_SPAIN to "es-ES",
                        ),
                        selected = state.preferences.recognitionLanguage,
                        recommended = RecognitionLanguage.AUTO,
                        onSelect = onRecognitionLanguageChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_follow_up),
                    description = stringResource(R.string.settings_follow_up_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            true to stringResource(R.string.choice_on),
                            false to stringResource(R.string.choice_off),
                        ),
                        selected = state.preferences.followUpEnabled,
                        recommended = true,
                        onSelect = onFollowUpChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_speak_chat),
                    description = stringResource(R.string.settings_speak_chat_help),
                ) {
                    ChoiceRow(
                        options = listOf(
                            true to stringResource(R.string.choice_on),
                            false to stringResource(R.string.choice_off),
                        ),
                        selected = state.preferences.speakChatReplies,
                        recommended = true,
                        onSelect = onSpeakChatChange,
                    )
                }
                SettingBlock(
                    title = stringResource(R.string.settings_stt_backend),
                    description = stringResource(R.string.settings_stt_backend_help),
                ) {
                    ChoiceRow(
                        options = choices(listOf("local", "openai"), state.config.sttBackend)
                            .map { it to it.providerName() },
                        selected = state.config.sttBackend,
                        recommended = "local",
                    ) { value -> onUpdate { it.copy(sttBackend = value) } }
                }
                SettingBlock(
                    title = stringResource(R.string.settings_tts_engine),
                    description = stringResource(R.string.settings_tts_help),
                ) {
                    ChoiceRow(
                        options = choices(listOf("kokoro", "piper", "openai"), state.config.ttsEngine)
                            .map { it to it.providerName() },
                        selected = state.config.ttsEngine,
                        recommended = "kokoro",
                    ) { value -> onUpdate { it.copy(ttsEngine = value) } }
                }
                AdvancedDisclosure(expanded = advanced, onToggle = { advanced = !advanced }) {
                    ModelField(stringResource(R.string.settings_stt_model), state.config.sttModel) { value ->
                        onUpdate { it.copy(sttModel = value) }
                    }
                    ModelField(stringResource(R.string.settings_tts_model), state.config.ttsModel) { value ->
                        onUpdate { it.copy(ttsModel = value) }
                    }
                    ModelField(stringResource(R.string.settings_tts_voice), state.config.ttsVoice) { value ->
                        onUpdate { it.copy(ttsVoice = value) }
                    }
                    BooleanChoice(
                        title = stringResource(R.string.settings_local_fallback),
                        value = state.config.sttFallbackToLocal,
                    ) { value -> onUpdate { it.copy(sttFallbackToLocal = value) } }
                    BooleanChoice(
                        title = stringResource(R.string.settings_tts_local_fallback),
                        value = state.config.ttsFallbackToLocal,
                    ) { value -> onUpdate { it.copy(ttsFallbackToLocal = value) } }
                }
            }

            Spacer(Modifier.height(Orbita.spacing.x3))
            DiagnosticsLink(onOpenDiagnostics)

            state.error?.let {
                Spacer(Modifier.height(Orbita.spacing.x4))
                Text(it, color = Orbita.colors.danger, style = OrbitaType.callout)
            }
            if (state.saved) {
                Spacer(Modifier.height(Orbita.spacing.x4))
                Text(stringResource(R.string.settings_saved), color = Orbita.colors.success)
            }
            Spacer(Modifier.height(Orbita.spacing.x6))
            PrimaryButton(
                label = if (state.saving) {
                    stringResource(R.string.settings_saving)
                } else {
                    stringResource(R.string.settings_save)
                },
                enabled = !state.saving && state.dirty,
                onClick = onSave,
            )
        }
        Spacer(Modifier.height(Orbita.spacing.x8))
    }
    }
}

@Composable
private fun PhoneCapabilityNode(
    state: SettingsUiState,
    onCodeChange: (String) -> Unit,
    onScan: () -> Unit,
    onEnrol: () -> Unit,
    onEnabledChange: (Boolean) -> Unit,
    onForget: () -> Unit,
    onNotificationAccess: () -> Unit,
    onCallPermission: () -> Unit,
) {
    SettingBlock(
        title = stringResource(R.string.settings_phone_node),
        description = stringResource(R.string.settings_phone_node_help),
    ) {
        if (!state.nodeEnrolled) {
            ModelField(
                stringResource(R.string.settings_phone_node_code),
                state.nodePairingCode,
                onCodeChange,
            )
            PrimaryButton(
                label = stringResource(R.string.settings_phone_node_scan),
                enabled = !state.nodeEnrolling,
                onClick = onScan,
            )
            PrimaryButton(
                label = stringResource(
                    if (state.nodeEnrolling) R.string.settings_phone_node_enrolling
                    else R.string.settings_phone_node_enrol,
                ),
                enabled = !state.nodeEnrolling && state.nodePairingCode.length == 8,
                onClick = onEnrol,
            )
        } else {
            Text(
                text = when (val connection = state.nodeConnection) {
                    is CapabilityConnectionState.Connected -> stringResource(
                        R.string.settings_phone_node_connected,
                        connection.generation,
                    )
                    CapabilityConnectionState.Connecting -> stringResource(R.string.settings_phone_node_connecting)
                    is CapabilityConnectionState.Failed -> stringResource(
                        R.string.settings_phone_node_retry,
                        connection.retryInSeconds,
                    )
                    is CapabilityConnectionState.Revoked -> stringResource(R.string.settings_phone_node_revoked)
                    CapabilityConnectionState.Disabled -> stringResource(R.string.settings_phone_node_disabled)
                    CapabilityConnectionState.Disconnected -> stringResource(R.string.settings_phone_node_disconnected)
                },
                style = OrbitaType.footnote,
                color = if (state.nodeConnection is CapabilityConnectionState.Connected) {
                    Orbita.colors.success
                } else {
                    Orbita.colors.fgTertiary
                },
            )
            ChoiceRow(
                options = listOf(
                    true to stringResource(R.string.choice_on),
                    false to stringResource(R.string.choice_off),
                ),
                selected = state.nodeEnabled,
                recommended = true,
                onSelect = onEnabledChange,
            )
            PrimaryButton(
                label = stringResource(R.string.settings_phone_node_forget),
                enabled = true,
                onClick = onForget,
            )
            Text(
                stringResource(R.string.settings_phone_node_forget_help),
                style = OrbitaType.footnote,
                color = Orbita.colors.fgTertiary,
            )
            SettingBlock(
                title = stringResource(R.string.settings_notification_access),
                description = stringResource(R.string.settings_notification_access_help),
            ) {
                PrimaryButton(
                    label = stringResource(
                        if (state.notificationAccess) R.string.settings_notification_access_manage
                        else R.string.settings_notification_access_open,
                    ),
                    enabled = true,
                    onClick = onNotificationAccess,
                )
            }
            SettingBlock(
                title = stringResource(R.string.settings_call_permission),
                description = stringResource(R.string.settings_call_permission_help),
            ) {
                PrimaryButton(
                    label = stringResource(
                        if (state.callPermission) R.string.settings_call_permission_manage
                        else R.string.settings_call_permission_allow,
                    ),
                    enabled = true,
                    onClick = onCallPermission,
                )
            }
        }
    }
}

@Composable
private fun SettingsCard(
    title: String,
    summary: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    content: @Composable () -> Unit,
) {
    val expansionState = stringResource(
        if (expanded) R.string.settings_expanded else R.string.settings_collapsed,
    )
    Column(
        Modifier.fillMaxWidth()
            .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.xxl))
            .clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel),
    ) {
        Row(
            Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onToggle)
                .semantics { stateDescription = expansionState }
                .padding(Orbita.spacing.x5),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, style = OrbitaType.title2, color = Orbita.colors.fgPrimary)
                Spacer(Modifier.height(Orbita.spacing.x1))
                Text(summary, style = OrbitaType.callout, color = Orbita.colors.fgTertiary)
            }
            Icon(
                Icons.Filled.ChevronRight,
                contentDescription = null,
                tint = Orbita.colors.fgTertiary,
                modifier = Modifier.rotate(if (expanded) 90f else 0f),
            )
        }
        AnimatedVisibility(expanded) {
            Column(
                Modifier.fillMaxWidth().padding(
                    start = Orbita.spacing.x5,
                    end = Orbita.spacing.x5,
                    bottom = Orbita.spacing.x5,
                ),
                verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x5),
            ) { content() }
        }
    }
}

@Composable
private fun SettingBlock(title: String, description: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x3)) {
        Text(title, style = OrbitaType.title3, color = Orbita.colors.fgPrimary)
        Text(description, style = OrbitaType.footnote, color = Orbita.colors.fgTertiary)
        content()
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun <T> ChoiceRow(
    options: List<Pair<T, String>>,
    selected: T,
    recommended: T? = null,
    onSelect: (T) -> Unit,
) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x2), verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        options.forEach { (value, label) ->
            ChoiceChip(label, selected == value, recommended == value, Role.RadioButton) { onSelect(value) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MultiChoiceRow(options: List<String>, selected: List<String>, onSelect: (String) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x2), verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        options.forEach { value ->
            ChoiceChip(value.providerName(), value in selected, false, Role.Checkbox) { onSelect(value) }
        }
    }
}

@Composable
private fun ChoiceChip(
    label: String,
    selected: Boolean,
    recommended: Boolean,
    role: Role,
    onClick: () -> Unit,
) {
    val selection = if (role == Role.Checkbox) {
        Modifier.toggleable(value = selected, role = role, onValueChange = { onClick() })
    } else {
        Modifier.selectable(selected = selected, role = role, onClick = onClick)
    }
    Column(
        Modifier.clip(RoundedCornerShape(Orbita.radii.pill))
            .background(if (selected) Orbita.colors.bgSelected else Orbita.colors.bgInset)
            .then(selection).heightIn(min = Orbita.sizing.minTouchTarget)
            .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x3),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x1),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Icon(
                    Icons.Filled.Check,
                    contentDescription = null,
                    tint = Orbita.colors.fgPrimary,
                    modifier = Modifier.size(16.dp),
                )
            }
            Text(
                label,
                style = OrbitaType.callout,
                color = if (selected) Orbita.colors.fgPrimary else Orbita.colors.fgSecondary,
            )
        }
        if (recommended) {
            Text(
                stringResource(R.string.settings_recommended).uppercase(),
                style = OrbitaType.caption,
                color = if (selected) Orbita.colors.fgSecondary else Orbita.colors.fgTertiary,
            )
        }
    }
}

@Composable
private fun ModelField(label: String, value: String, onChange: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        Text(label, style = OrbitaType.footnote, color = Orbita.colors.fgTertiary)
        TextField(
            value = value,
            onValueChange = onChange,
            singleLine = true,
            textStyle = OrbitaType.mono.copy(color = Orbita.colors.fgPrimary),
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false),
            shape = RoundedCornerShape(Orbita.radii.lg),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Orbita.colors.bgInset,
                unfocusedContainerColor = Orbita.colors.bgInset,
                focusedTextColor = Orbita.colors.fgPrimary,
                unfocusedTextColor = Orbita.colors.fgPrimary,
                cursorColor = Orbita.colors.accent,
                focusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
                unfocusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun AdvancedDisclosure(expanded: Boolean, onToggle: () -> Unit, content: @Composable () -> Unit) {
    val expansionState = stringResource(
        if (expanded) R.string.settings_expanded else R.string.settings_collapsed,
    )
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x4)) {
        Row(
            Modifier.clip(RoundedCornerShape(Orbita.radii.pill)).background(Orbita.colors.bgInset)
                .clickable(role = Role.Button, onClick = onToggle)
                .semantics { stateDescription = expansionState }
                .heightIn(min = Orbita.sizing.minTouchTarget)
                .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x2),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(stringResource(R.string.settings_advanced), style = OrbitaType.callout, color = Orbita.colors.fgSecondary)
            Icon(
                Icons.Filled.ChevronRight,
                contentDescription = null,
                tint = Orbita.colors.fgTertiary,
                modifier = Modifier.rotate(if (expanded) 90f else 0f),
            )
        }
        AnimatedVisibility(expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x5)) { content() }
        }
    }
}

@Composable
private fun BooleanChoice(title: String, value: Boolean, onChange: (Boolean) -> Unit) {
    SettingBlock(title, stringResource(R.string.settings_fallback_toggle_help)) {
        ChoiceRow(
            options = listOf(true to stringResource(R.string.choice_on), false to stringResource(R.string.choice_off)),
            selected = value,
            onSelect = onChange,
        )
    }
}

/**
 * Live presence, in the same shape the desktop uses: a dot and a sentence. A
 * switch whose effect you cannot see is a switch nobody trusts.
 */
@Composable
private fun NodePresence(config: MobileConfig) {
    val up = config.nodeAvailable
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.size(7.dp)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(if (up) Orbita.colors.success else Orbita.colors.fgQuaternary),
        )
        Spacer(Modifier.padding(Orbita.spacing.x1))
        Text(
            text = when {
                !up -> stringResource(R.string.settings_nodes_none)
                config.nodeName.isNotBlank() ->
                    stringResource(R.string.settings_nodes_using, config.nodeName)
                // Connected, but its policy forbids hosting: saying "available"
                // here would promise work it would refuse.
                else -> stringResource(R.string.settings_nodes_tools_only)
            },
            style = OrbitaType.footnote,
            color = if (up) Orbita.colors.fgSecondary else Orbita.colors.fgTertiary,
        )
    }
}

@Composable
private fun nodeSummary(config: MobileConfig): String = when {
    !config.nodesEnabled -> stringResource(R.string.settings_nodes_off)
    config.nodeName.isNotBlank() -> config.nodeName
    config.nodeAvailable -> stringResource(R.string.settings_nodes_tools_only)
    else -> stringResource(R.string.settings_nodes_none)
}

@Composable
private fun ProviderStatus(provider: String, configured: Map<String, Boolean>) {
    if (provider !in setOf("anthropic", "openai", "gemini", "deepseek")) return
    val ready = configured[provider] == true
    Text(
        text = stringResource(
            if (ready) R.string.settings_provider_ready else R.string.settings_provider_needs_key,
        ),
        style = OrbitaType.footnote,
        color = if (ready) Orbita.colors.success else Orbita.colors.warning,
    )
}

@Composable
private fun DiagnosticsLink(onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.xxl))
            .clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel).clickable(role = Role.Button, onClick = onClick)
            .padding(Orbita.spacing.x5),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.Troubleshoot, contentDescription = null, tint = Orbita.colors.fgTertiary)
        Spacer(Modifier.padding(Orbita.spacing.x2))
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(R.string.settings_diagnostics),
                style = OrbitaType.title3,
                color = Orbita.colors.fgPrimary,
            )
            Text(stringResource(R.string.settings_diagnostics_help), style = OrbitaType.footnote, color = Orbita.colors.fgTertiary)
        }
        Icon(Icons.Filled.ChevronRight, contentDescription = null, tint = Orbita.colors.fgTertiary)
    }
}

@Composable
private fun PrimaryButton(label: String, enabled: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth().heightIn(min = Orbita.sizing.controlHeight)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(if (enabled) Orbita.colors.accent else Orbita.colors.bgElevated)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = OrbitaType.title3, color = if (enabled) Orbita.colors.fgOnAccent else Orbita.colors.fgQuaternary)
    }
}

@Composable
private fun languageLabel(value: AppLanguage) = when (value) {
    AppLanguage.ENGLISH -> stringResource(R.string.language_english)
    AppLanguage.SPANISH -> stringResource(R.string.language_spanish)
}

@Composable
private fun themeLabel(value: ThemePreference) = when (value) {
    ThemePreference.SYSTEM -> stringResource(R.string.theme_system)
    ThemePreference.DARK -> stringResource(R.string.theme_dark)
    ThemePreference.LIGHT -> stringResource(R.string.theme_light)
}

@Composable
private fun recognitionSummary(state: SettingsUiState): String = when (state.preferences.recognitionMode) {
    RecognitionMode.ANDROID -> stringResource(R.string.recognition_android)
    RecognitionMode.SERVER -> stringResource(R.string.recognition_server)
}

private fun String.providerName(): String = replaceFirstChar { it.uppercase() }

private fun choices(defaults: List<String>, current: String): List<String> =
    (defaults + current).filter(String::isNotBlank).distinct()

private fun choices(defaults: List<String>, current: List<String>): List<String> =
    (defaults + current).filter(String::isNotBlank).distinct()

@Preview(name = "Settings dark", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun SettingsDarkPreview() {
    OrbitaTheme(darkTheme = true) { SettingsPreviewContent() }
}

@Preview(name = "Settings light", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun SettingsLightPreview() {
    OrbitaTheme(darkTheme = false) { SettingsPreviewContent() }
}

@Composable
private fun SettingsPreviewContent() {
    SettingsScreen(
        state = SettingsUiState(
            config = MobileConfig(
                provider = "ollama",
                models = mapOf("ollama" to "llama3.2"),
                fallbackOrder = listOf("anthropic"),
                sttBackend = "local",
                ttsEngine = "kokoro",
            ),
            loaded = true,
        ),
        onLoad = {},
        onUpdate = {},
        onSave = {},
        onAppLanguageChange = {},
        onRecognitionModeChange = {},
        onRecognitionLanguageChange = {},
        onSpeechOutputModeChange = {},
        onFollowUpChange = {},
        onSpeakChatChange = {},
        onThemeChange = {},
        onNodeCodeChange = {},
        onNodeQr = {},
        onEnrolNode = {},
        onNodeEnabledChange = {},
        onForgetNode = {},
        onNodePermissionsChanged = {},
        onOpenDiagnostics = {},
    )
}
