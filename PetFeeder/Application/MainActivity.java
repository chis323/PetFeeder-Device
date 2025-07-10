package com.example.wifi;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.net.URL;

public class MainActivity extends AppCompatActivity {

    private static final int PI_PORT = 5000;
    private static final String TAG = "PiController";
    private static final String AZURE_LOG_URL = "https://chis32.blob.core.windows.net/jsondata/dispense_logs(s).json";

    private Socket socket;
    private OutputStream out;
    private boolean isConnected = false;
    private String currentPiIp = "";

    private TextView connectionStatus;
    private EditText ipAddressInput;
    private Button btnConnect, btnUp, btnDown, btnAuto, btnViewLog, btnCloseLog;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        initViews();
        setupButtonListeners();
    }

    private void initViews() {
        connectionStatus = findViewById(R.id.connectionStatus);
        ipAddressInput = findViewById(R.id.ipAddressInput);
        btnConnect = findViewById(R.id.btnConnect);
        btnUp = findViewById(R.id.btnUp);
        btnDown = findViewById(R.id.btnDown);
        btnAuto = findViewById(R.id.btnAuto);
        btnViewLog = findViewById(R.id.btnViewLog);
        btnCloseLog = findViewById(R.id.btnCloseLog);
        setControlButtonsEnabled(false);
    }

    private void setupButtonListeners() {
        btnConnect.setOnClickListener(v -> attemptConnection());
        btnUp.setOnClickListener(v -> sendCommand("Up"));
        btnDown.setOnClickListener(v -> sendCommand("Down"));
        btnAuto.setOnClickListener(v -> sendCommand("Auto"));
        btnViewLog.setOnClickListener(v -> fetchAzureLog());
        btnCloseLog.setOnClickListener(v -> closeLogView());
    }

    private void attemptConnection() {
        String ipAddress = ipAddressInput.getText().toString().trim();
        if (ipAddress.isEmpty()) {
            showToast("Please enter an IP address");
            return;
        }

        if (!isNetworkAvailable()) {
            showToast("No network connection available");
            return;
        }

        connectToPi(ipAddress);
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo activeNetwork = cm.getActiveNetworkInfo();
        return activeNetwork != null && activeNetwork.isConnected();
    }

    private void connectToPi(String ipAddress) {
        currentPiIp = ipAddress;
        updateStatus("Connecting to " + ipAddress + "...");

        new Thread(() -> {
            try {
                closePreviousConnection();
                socket = new Socket();
                socket.connect(new InetSocketAddress(ipAddress, PI_PORT), 5000);
                out = socket.getOutputStream();

                runOnUiThread(() -> {
                    isConnected = true;
                    updateStatus("Connected to " + ipAddress);
                    setControlButtonsEnabled(true);
                });

                new Thread(this::sendKeepAlives).start();

            } catch (SocketTimeoutException e) {
                handleConnectionError("Timeout: Check Pi is running");
            } catch (IOException e) {
                handleConnectionError("Error: " + e.getMessage());
            }
        }).start();
    }

    private void closePreviousConnection() throws IOException {
        if (socket != null && !socket.isClosed()) {
            socket.close();
        }
    }

    private void sendKeepAlives() {
        try {
            while (isConnected) {
                Thread.sleep(30000);
                sendCommand("PING");
            }
        } catch (InterruptedException e) {
            Log.d(TAG, "Keep-alive interrupted");
        }
    }

    private void sendCommand(String cmd) {
        if (!isConnected) {
            showToast("Not connected to Pi");
            return;
        }

        new Thread(() -> {
            try {
                out.write((cmd + "\n").getBytes());
                out.flush();
                Log.d(TAG, "Command sent: " + cmd);
            } catch (IOException e) {
                handleConnectionError("Send failed: " + e.getMessage());
                attemptReconnect();
            }
        }).start();
    }

    private void attemptReconnect() {
        if (!currentPiIp.isEmpty()) {
            runOnUiThread(() -> connectToPi(currentPiIp));
        }
    }

    private void handleConnectionError(String message) {
        runOnUiThread(() -> {
            isConnected = false;
            updateStatus("Connection failed");
            showToast(message);
            setControlButtonsEnabled(false);
        });
    }

    private void setControlButtonsEnabled(boolean enabled) {
        btnUp.setEnabled(enabled);
        btnDown.setEnabled(enabled);
        btnAuto.setEnabled(enabled);
        btnConnect.setEnabled(!enabled);
        ipAddressInput.setEnabled(!enabled);
    }

    private void updateStatus(String message) {
        connectionStatus.setText(message);
    }

    private void showToast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private void fetchAzureLog() {
        new Thread(() -> {
            try {
                URL url = new URL(AZURE_LOG_URL);
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");

                int responseCode = connection.getResponseCode();
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    InputStream input = new BufferedInputStream(connection.getInputStream());
                    String result = convertStreamToString(input);
                    runOnUiThread(() -> displayLog(result));
                } else {
                    runOnUiThread(() -> showToast("Error fetching log: " + responseCode));
                }
            } catch (IOException e) {
                runOnUiThread(() -> showToast("Failed to fetch log: " + e.getMessage()));
            }
        }).start();
    }

    private String convertStreamToString(InputStream inputStream) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line);
        }
        inputStream.close();
        return sb.toString();
    }

    private void displayLog(String json) {
        try {
            JSONArray logs = new JSONArray(json);
            LinearLayout logContainer = findViewById(R.id.logContainer);
            logContainer.setVisibility(View.VISIBLE);
            logContainer.removeAllViews();

            if (logs.length() == 0) {
                addLogCard(logContainer, "No logs available.", "N/A");
                return;
            }

            for (int i = 0; i < logs.length(); i++) {
                JSONObject entry = logs.getJSONObject(i);
                String timestamp = entry.optString("timestamp", "N/A");
                String item = entry.optString("item", "N/A");

                String message;
                switch (item.trim().toLowerCase()) {
                    case "food":
                        message = "The cat received food.";
                        break;
                    case "water":
                        message = "The cat received water.";
                        break;
                    case "cat_detected":
                        message = "Cat detected.";
                        break;
                    default:
                        message = "Unknown event.";
                }

                addLogCard(logContainer, message, timestamp);
            }
        } catch (JSONException e) {
            Toast.makeText(this, "Failed to parse log data.", Toast.LENGTH_SHORT).show();
        }
    }

    private void addLogCard(LinearLayout container, String message, String timestamp) {
        CardView cardView = new CardView(this);
        cardView.setCardElevation(8);
        cardView.setRadius(20);
        cardView.setCardBackgroundColor(Color.WHITE);

        GradientDrawable border = new GradientDrawable();
        border.setColor(Color.WHITE);
        border.setStroke(6, Color.parseColor("#9C27B0")); // Purple stroke
        border.setCornerRadius(20);
        cardView.setBackground(border);

        cardView.setContentPadding(10, 10, 10, 10);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(30, 20, 30, 20);

        TextView messageView = new TextView(this);
        messageView.setText(message);
        messageView.setTextSize(18);
        messageView.setTextColor(Color.BLACK);

        TextView timeView = new TextView(this);
        timeView.setText(timestamp);
        timeView.setTextSize(14);
        timeView.setTextColor(Color.DKGRAY);

        layout.addView(messageView);
        layout.addView(timeView);
        cardView.addView(layout);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 16, 0, 16);
        cardView.setLayoutParams(params);

        container.addView(cardView);
    }

    private void closeLogView() {
        LinearLayout logContainer = findViewById(R.id.logContainer);
        logContainer.setVisibility(View.GONE);
        showToast("Log view closed");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try {
            if (socket != null) {
                socket.close();
            }
        } catch (IOException e) {
            Log.e(TAG, "Error closing socket", e);
        }
    }
}
