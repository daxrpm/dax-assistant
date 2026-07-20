package com.dax.assistant.ui.setup

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.res.stringResource
import com.dax.assistant.R
import com.dax.assistant.ui.SetupUiState
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

/**
 * First run: point the phone at a backend and pair it.
 *
 * The phone never asks for the account password. A client that is already
 * signed in — the desktop app or the web UI — mints a one-time pairing code,
 * and this screen redeems it once for a device credential that lives in the
 * keystore. That is why the copy talks about a code from another device rather
 * than offering a password field: there is deliberately nowhere to type one.
 */
@Composable
fun SetupScreen(
    state: SetupUiState,
    onUrlChange: (String) -> Unit,
    onCodeChange: (String) -> Unit,
    onEnrol: () -> Unit,
    onScanQr: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Orbita.colors.bgWindow)
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x8),
    ) {
        Text(
            text = stringResource(R.string.setup_title),
            style = OrbitaType.largeTitle,
            color = Orbita.colors.fgPrimary,
            modifier = Modifier.semantics { heading() },
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = stringResource(R.string.setup_intro),
            style = OrbitaType.callout,
            color = Orbita.colors.fgTertiary,
        )

        Spacer(Modifier.height(Orbita.spacing.x8))

        StepCard(number = "1", title = stringResource(R.string.setup_step_backend)) {
            Field(
                label = stringResource(R.string.setup_backend),
                value = state.backendUrl,
                onValueChange = onUrlChange,
                placeholder = stringResource(R.string.setup_backend_hint),
                keyboardType = KeyboardType.Uri,
            )
        }

        Spacer(Modifier.height(Orbita.spacing.x3))

        StepCard(number = "2", title = stringResource(R.string.setup_step_pair)) {
            Field(
                label = stringResource(R.string.setup_code),
                value = state.pairingCode,
                onValueChange = onCodeChange,
                placeholder = stringResource(R.string.setup_code_hint),
                capitalization = KeyboardCapitalization.Characters,
            )
            Text(
                text = stringResource(R.string.setup_code_help),
                style = OrbitaType.footnote,
                color = Orbita.colors.fgQuaternary,
            )
        }

        state.error?.let { error ->
            Spacer(Modifier.height(Orbita.spacing.x4))
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(Orbita.radii.lg))
                    .background(Orbita.colors.danger.copy(alpha = 0.14f))
                    .padding(Orbita.spacing.x4),
            ) {
                Text(text = error, style = OrbitaType.callout, color = Orbita.colors.danger)
            }
        }

        Spacer(Modifier.height(Orbita.spacing.x8))

        val formValid = state.backendUrl.isNotBlank() && isValidPairingCode(state.pairingCode)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = Orbita.sizing.controlHeight)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(
                    if (state.enrolling || !formValid) Orbita.colors.bgElevated else Orbita.colors.accent,
                )
                .clickable(enabled = !state.enrolling && formValid, role = Role.Button, onClick = onEnrol)
                .padding(Orbita.spacing.x4),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = if (state.enrolling) stringResource(R.string.setup_pairing) else stringResource(R.string.setup_pair),
                style = OrbitaType.title3,
                color = if (state.enrolling || !formValid) {
                    Orbita.colors.fgQuaternary
                } else {
                    Orbita.colors.fgOnAccent
                },
            )
        }

        Spacer(Modifier.height(Orbita.spacing.x3))

        Box(
            modifier = Modifier.fillMaxWidth().heightIn(min = Orbita.sizing.controlHeight)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(Orbita.colors.bgElevated)
                .clickable(role = Role.Button, onClick = onScanQr)
                .padding(Orbita.spacing.x4),
            contentAlignment = Alignment.Center,
        ) {
            Text(stringResource(R.string.setup_scan_qr), style = OrbitaType.title3, color = Orbita.colors.fgSecondary)
        }
    }
}

@Composable
fun PermissionSetupScreen(onContinue: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().background(Orbita.colors.bgWindow).systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x8),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            stringResource(R.string.setup_permissions_title),
            style = OrbitaType.largeTitle,
            color = Orbita.colors.fgPrimary,
            modifier = Modifier.semantics { heading() },
        )
        Spacer(Modifier.height(Orbita.spacing.x3))
        Text(
            stringResource(R.string.setup_permissions_intro),
            style = OrbitaType.callout,
            color = Orbita.colors.fgSecondary,
        )
        Spacer(Modifier.height(Orbita.spacing.x6))
        StepCard(number = "3", title = stringResource(R.string.setup_permissions_step)) {
            Text(
                stringResource(R.string.setup_permissions_detail),
                style = OrbitaType.body,
                color = Orbita.colors.fgTertiary,
            )
        }
        Spacer(Modifier.height(Orbita.spacing.x8))
        Box(
            Modifier.fillMaxWidth().heightIn(min = Orbita.sizing.controlHeight)
                .clip(RoundedCornerShape(Orbita.radii.pill)).background(Orbita.colors.accent)
                .clickable(role = Role.Button, onClick = onContinue),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                stringResource(R.string.setup_permissions_continue),
                style = OrbitaType.title3,
                color = Orbita.colors.fgOnAccent,
            )
        }
    }
}

@Composable
private fun StepCard(number: String, title: String, content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel).padding(Orbita.spacing.x5),
        verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x4),
    ) {
        androidx.compose.foundation.layout.Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.clip(RoundedCornerShape(Orbita.radii.pill))
                    .background(Orbita.colors.accentDim)
                    .padding(horizontal = Orbita.spacing.x3, vertical = Orbita.spacing.x1),
            ) {
                Text(number, style = OrbitaType.monoSmall, color = Orbita.colors.accent)
            }
            Spacer(Modifier.padding(Orbita.spacing.x2))
            Text(title, style = OrbitaType.title3, color = Orbita.colors.fgPrimary)
        }
        content()
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType = KeyboardType.Text,
    capitalization: KeyboardCapitalization = KeyboardCapitalization.None,
) {
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        Text(text = label.uppercase(), style = OrbitaType.label, color = Orbita.colors.fgTertiary)
        TextField(
            value = value,
            onValueChange = onValueChange,
            placeholder = {
                Text(placeholder, style = OrbitaType.callout, color = Orbita.colors.fgQuaternary)
            },
            singleLine = true,
            textStyle = OrbitaType.mono.copy(color = Orbita.colors.fgPrimary),
            keyboardOptions = KeyboardOptions(
                keyboardType = keyboardType,
                capitalization = capitalization,
                autoCorrectEnabled = false,
            ),
            shape = RoundedCornerShape(Orbita.radii.lg),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Orbita.colors.bgInset,
                unfocusedContainerColor = Orbita.colors.bgInset,
                focusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
                unfocusedIndicatorColor = androidx.compose.ui.graphics.Color.Transparent,
                cursorColor = Orbita.colors.accent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
