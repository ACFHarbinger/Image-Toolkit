#!/usr/bin/env sh

# --- Standard Gradle Wrapper Script Content ---

# This script ensures Gradle is downloaded and executed using the correct version
# defined in gradle-wrapper.properties.
# Set the path to the Java executable

if [ -n "$JAVA_HOME" ] ; then
    JAVA_CMD="$JAVA_HOME/bin/java"
else
    JAVA_CMD="java"
fi

# Check if Java is available

if ! command -v "$JAVA_CMD" >/dev/null 2>&1; then
    echo "ERROR: Java is not installed or JAVA_HOME is not set correctly."
    echo "Please ensure Java 21 or later is installed and accessible."
    exit 1
fi

# Determine the directory of the script

APP_HOME=$(dirname "$0")

# If the wrapper jar does not exist, download it (this part is usually handled by the wrapper itself)

# For simplicity and standard compliance, we rely on the wrapper environment.

# Execute the wrapper

exec "$JAVA_CMD" -Dgradle.user.home="$APP_HOME"/.gradle -classpath "$APP_HOME/gradle/wrapper/gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain "$@"