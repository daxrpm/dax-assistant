#!/usr/bin/env bash
# Toolchain for the Android build.
#
# Everything lives on the external volume on purpose: the primary disk sits at
# ~94% and a Gradle cache plus AGP intermediates would fill it.
export JAVA_HOME=/run/media/daxrpm/fedora/home/daxrpm/toolchain/jdk-21.0.11+10
export ANDROID_HOME=/run/media/daxrpm/fedora/home/daxrpm/Android/Sdk
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME=/run/media/daxrpm/fedora/home/daxrpm/toolchain/gradle-home
export PATH="$JAVA_HOME/bin:/run/media/daxrpm/fedora/home/daxrpm/toolchain/gradle-8.11.1/bin:$ANDROID_HOME/platform-tools:$PATH"
