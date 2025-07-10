<?xml version="1.0" encoding="utf-8"?>
<LinearLayout 
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="24dp"
    android:background="#FFFFFF">

    <!-- Connection Status -->
    <TextView
        android:id="@+id/connectionStatus"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Not connected"
        android:textStyle="bold"
        android:textSize="20sp"
        android:textColor="#FF5722"
        android:gravity="center_horizontal"
        android:paddingBottom="12dp" />

    <!-- IP Address Input -->
    <EditText
        android:id="@+id/ipAddressInput"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Enter Raspberry Pi IP address"
        android:inputType="text"
        android:background="@android:drawable/edit_text"
        android:padding="12dp"
        android:layout_marginBottom="12dp" />

    <!-- Connect Button -->
    <Button
        android:id="@+id/btnConnect"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Connect to Pi"
        android:backgroundTint="#4CAF50"
        android:textColor="#FFFFFF"
        android:layout_marginBottom="16dp" />

    <!-- Control Buttons -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:weightSum="3"
        android:gravity="center"
        android:layout_marginBottom="16dp">

        <Button
            android:id="@+id/btnUp"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="Food"
            android:backgroundTint="#03A9F4"
            android:textColor="#FFFFFF"
            android:layout_marginEnd="4dp" />

        <Button
            android:id="@+id/btnDown"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="Water"
            android:backgroundTint="#03A9F4"
            android:textColor="#FFFFFF"
            android:layout_marginStart="2dp"
            android:layout_marginEnd="2dp" />

        <Button
            android:id="@+id/btnAuto"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="Auto Feed"
            android:backgroundTint="#03A9F4"
            android:textColor="#FFFFFF"
            android:layout_marginStart="4dp" />
    </LinearLayout>

    <!-- View Log Button -->
    <Button
        android:id="@+id/btnViewLog"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="View Eating History"
        android:backgroundTint="#9C27B0"
        android:textColor="#FFFFFF"
        android:layout_marginBottom="12dp" />

    <!-- Close Log Button (formerly Delete Log) -->
    <Button
        android:id="@+id/btnCloseLog"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Close Log View"
        android:backgroundTint="#D32F2F"
        android:textColor="#FFFFFF"
        android:layout_marginBottom="12dp" />

    <!-- Scrollable Log Display -->
    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:background="#ECEFF1"
        android:padding="8dp"
        android:layout_marginTop="8dp"
        android:layout_marginBottom="8dp"
        android:scrollbars="vertical">

        <LinearLayout
            android:id="@+id/logContainer"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical" />
    </ScrollView>
</LinearLayout>
