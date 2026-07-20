package com.dax.assistant.ui.settings

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.dax.assistant.R
import com.dax.assistant.mobileapi.MobileConfig
import com.dax.assistant.preferences.AppLanguage
import com.dax.assistant.preferences.RecognitionLanguage
import com.dax.assistant.preferences.RecognitionMode
import com.dax.assistant.preferences.ThemePreference
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

private enum class SettingsSection { INTERFACE, INTELLIGENCE, SPEECH }

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    onLoad: () -> Unit,
    onUpdate: ((MobileConfig) -> MobileConfig) -> Unit,
    onSave: () -> Unit,
    onAppLanguageChange: (AppLanguage) -> Unit,
    onRecognitionModeChange: (RecognitionMode) -> Unit,
    onRecognitionLanguageChange: (RecognitionLanguage) -> Unit,
    onThemeChange: (ThemePreference) -> Unit,
    onOpenDiagnostics: () -> Unit,
    modifier: Modifier = Modifier,
) {
    androidx.compose.runtime.LaunchedEffect(Unit) { if (!state.loaded) onLoad() }
    var expanded by remember { mutableStateOf<SettingsSection?>(null) }
    var advanced by remember { mutableStateOf(false) }

    Column(
        modifier.fillMaxSize().background(Orbita.colors.bgWindow)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x6),
    ) {
        Text(stringResource(R.string.settings_title), style = OrbitaType.largeTitle)
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
                enabled = !state.saving,
                onClick = onSave,
            )
        }
        Spacer(Modifier.height(Orbita.spacing.x8))
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
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel),
    ) {
        Row(
            Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onToggle)
                .padding(Orbita.spacing.x5),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, style = OrbitaType.title2)
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
        Text(title, style = OrbitaType.title3)
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
            ChoiceChip(label, selected == value, recommended == value) { onSelect(value) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MultiChoiceRow(options: List<String>, selected: List<String>, onSelect: (String) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x2), verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        options.forEach { value -> ChoiceChip(value.providerName(), value in selected, false) { onSelect(value) } }
    }
}

@Composable
private fun ChoiceChip(label: String, selected: Boolean, recommended: Boolean, onClick: () -> Unit) {
    Column(
        Modifier.clip(RoundedCornerShape(Orbita.radii.pill))
            .background(if (selected) Orbita.colors.bgElevated else Orbita.colors.bgInset)
            .clickable(role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x3),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(label, style = OrbitaType.callout, color = if (selected) Orbita.colors.fgPrimary else Orbita.colors.fgSecondary)
        if (recommended) {
            Text(stringResource(R.string.settings_recommended).uppercase(), style = OrbitaType.caption, color = Orbita.colors.accent)
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
            textStyle = OrbitaType.mono,
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false),
            shape = RoundedCornerShape(Orbita.radii.lg),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Orbita.colors.bgInset,
                unfocusedContainerColor = Orbita.colors.bgInset,
                focusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
                unfocusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun AdvancedDisclosure(expanded: Boolean, onToggle: () -> Unit, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x4)) {
        Row(
            Modifier.clip(RoundedCornerShape(Orbita.radii.pill)).background(Orbita.colors.bgInset)
                .clickable(role = Role.Button, onClick = onToggle)
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
        Modifier.fillMaxWidth().clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel).clickable(role = Role.Button, onClick = onClick)
            .padding(Orbita.spacing.x5),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.Troubleshoot, contentDescription = null, tint = Orbita.colors.fgTertiary)
        Spacer(Modifier.padding(Orbita.spacing.x2))
        Column(Modifier.weight(1f)) {
            Text(stringResource(R.string.settings_diagnostics), style = OrbitaType.title3)
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
