# bitcoin_forecast_pipeline_updated.py
# Run: python bitcoin_forecast_pipeline_updated.py
# Requires: pandas, numpy, matplotlib, statsmodels, prophet, xgboost, scikit-learn, ta (or pandas_ta), torch, yfinance

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.preprocessing import StandardScaler
import ta
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
import torch.optim as optim
import yfinance as yf

# -------------------------
# Helpers
# -------------------------
def compute_technical_indicators(df):
    """Add common technical indicators (in-place) using 'Price' as close."""
    # --- FIX MultiIndex Columns ---
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
    else:
        df.columns = df.columns.str.strip()
    # If Price column missing, use Close
    if 'Price' not in df.columns:
        if 'Close' in df.columns:
            df['Price'] = df['Close']
        else:
            raise KeyError("No 'Price' or 'Close' column found in DataFrame.")

    close = df['Price']
    high = df['High']
    low = df['Low']

    # Technical indicators
    df['SMA_10'] = ta.trend.sma_indicator(close, window=10)
    df['SMA_50'] = ta.trend.sma_indicator(close, window=50)
    df['RSI_14'] = ta.momentum.rsi(close, window=14)
    df['BB_middle'] = ta.volatility.bollinger_mavg(close, window=20)
    df['BB_upper'] = ta.volatility.bollinger_hband(close, window=20)
    df['BB_lower'] = ta.volatility.bollinger_lband(close, window=20)
    df['ATR_14'] = ta.volatility.average_true_range(high, low, close, window=14)
    df['MACD'] = ta.trend.macd(close)
    df['MACD_signal'] = ta.trend.macd_signal(close)
    df['MACD_diff'] = ta.trend.macd_diff(close)

    # Weighted moving average
    def wma(series, window):
        weights = np.arange(1, window + 1)
        return series.rolling(window).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    df['WMA_10'] = wma(close, window=10)

    # Returns
    df['ret'] = df['Price'].pct_change()
    df['logret'] = np.log(df['Price']).diff()

    # Lags
    n_lags = 4
    for lag in range(1, n_lags + 1):
        df[f'lag_price_{lag}'] = df['Price'].shift(lag)
        df[f'lag_ret_{lag}'] = df['ret'].shift(lag)

    return df


def evaluate_forecast(y_true, y_pred, today_price):
    """Return dict with MAE, RMSE, directional accuracy, cumulative return, and approx Sharpe."""
    y_true = np.asarray(y_true).astype(float)
    y_pred = np.asarray(y_pred).astype(float)
    tp = np.asarray(today_price).astype(float)
    if tp.shape == ():
        tp = np.array([tp])  # make 1d for single-step cases

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    direction_actual = np.sign(y_true - tp)
    direction_pred = np.sign(y_pred - tp)
    dir_acc = float(np.mean(direction_actual == direction_pred))

    pred_signal = (y_pred > tp).astype(int)
    actual_returns = (y_true - tp) / tp
    strategy_returns = pred_signal * actual_returns

    cum_return = (1 + pd.Series(strategy_returns)).cumprod().iloc[-1] - 1
    sharpe = (np.mean(strategy_returns) / (np.std(strategy_returns) + 1e-12)) * np.sqrt(252) if np.std(strategy_returns) > 0 else np.nan

    return {'MAE': mae, 'RMSE': rmse, 'DirAcc': dir_acc, 'CumReturn': float(cum_return), 'Sharpe': float(sharpe)}

class LSTM(nn.Module):
    def __init__(self, input_size=1, hidden_layer_size=50, output_size=1):
        super().__init__()
        self.hidden_layer_size = hidden_layer_size
        self.lstm = nn.LSTM(input_size, hidden_layer_size)
        self.linear = nn.Linear(hidden_layer_size, output_size)

    def forward(self, input_seq):
        # input_seq: (seq_len, 1, input_size)
        h0 = torch.zeros(1, 1, self.hidden_layer_size)
        c0 = torch.zeros(1, 1, self.hidden_layer_size)
        lstm_out, _ = self.lstm(input_seq, (h0, c0))
        prediction = self.linear(lstm_out[-1])  # last time step
        return prediction

# -------------------------
# 0. Load & clean (yfinance through 2025-08-15)
# -------------------------
print("Fetching latest Bitcoin data up to 2025-08-15...")
df = yf.download('BTC-USD', start='2023-01-01', end='2025-08-16')

# Fix MultiIndex columns and rename
if isinstance(df.columns, pd.MultiIndex):
    df.columns = [col[0] for col in df.columns.values]

df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.rename(columns={'Close': 'Price'}, inplace=True)


# -------------------------
# 1. Feature engineering
# -------------------------
compute_technical_indicators(df)
df = df.dropna().copy()

# -------------------------
# 2. Train/test split (last day as test)
# -------------------------
test_size = 1
train_df = df.iloc[:-test_size].copy()
test_df = df.iloc[-test_size:].copy()
print(f"Rows - total: {len(df)}, train: {len(train_df)}, test: {len(test_df)}")
print(f"Test date: {test_df.index[0].date()}")

# -------------------------
# 3. ARIMA
# -------------------------
print("Fitting ARIMA...")
arima_model = ARIMA(train_df['Price'], order=(5, 1, 2))
arima_result = arima_model.fit()
arima_forecast = arima_result.forecast(steps=test_size)
arima_eval = evaluate_forecast(test_df['Price'].values, arima_forecast.values, np.array([train_df['Price'].iloc[-1]]))

# Plot (optional)
plt.figure(figsize=(10,3))
plt.plot(train_df.index, train_df['Price'], label='Train')
plt.plot(test_df.index, test_df['Price'], 'o', label='Test')
plt.plot(test_df.index, arima_forecast.values, 'x', label='ARIMA Forecast')
plt.title('ARIMA vs Actual (last day)')
plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()

# -------------------------
# 4. Prophet
# -------------------------
print("Fitting Prophet...")
prophet_train = train_df.reset_index()[['Date', 'Price']].rename(columns={'Date':'ds','Price':'y'}) if 'Date' in train_df.reset_index().columns else train_df.reset_index().rename(columns={'index':'ds','Price':'y'})
prophet_model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
prophet_model.fit(prophet_train[['ds','y']])
future = prophet_model.make_future_dataframe(periods=test_size, freq='D')
forecast_prophet = prophet_model.predict(future)
forecast_prophet.set_index('ds', inplace=True)
prophet_pred = forecast_prophet.loc[test_df.index, 'yhat'].values
prophet_eval = evaluate_forecast(test_df['Price'].values, prophet_pred, np.array([train_df['Price'].iloc[-1]]))

plt.figure(figsize=(10,3))
plt.plot(train_df.index, train_df['Price'], label='Train')
plt.plot(test_df.index, test_df['Price'], 'o', label='Test')
plt.plot(test_df.index, prophet_pred, 'x', label='Prophet Forecast')
plt.title('Prophet vs Actual (last day)')
plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()

# -------------------------
# 5. XGBoost (supervised regression on technicals & lags)
# -------------------------
print("Fitting XGBoost...")
# Use all engineered features except raw OHLCV and target
feature_cols = [c for c in train_df.columns if c not in ['Price', 'Open', 'High', 'Low', 'Volume']]
X_train = train_df[feature_cols].copy()
y_train = train_df['Price'].copy()
X_test  = test_df[feature_cols].copy()
y_test  = test_df['Price'].copy()

# Scale features (trees don't require it, but OK esp. when mixing with continuous indicators)
scaler_xgb = StandardScaler()
X_train_sc = scaler_xgb.fit_transform(X_train)
X_test_sc  = scaler_xgb.transform(X_test)

# Small grid; keep fast
tscv = TimeSeriesSplit(n_splits=3)
param_grid = {
    'n_estimators': [150, 300],
    'max_depth': [3, 5],
    'learning_rate': [0.03, 0.07]
}
xgb_base = xgb.XGBRegressor(objective='reg:squarederror', subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)
grid = GridSearchCV(xgb_base, param_grid, scoring='neg_mean_absolute_error', cv=tscv, n_jobs=1)
grid.fit(X_train_sc, y_train)
xgb_best = grid.best_estimator_
xgb_best.fit(X_train_sc, y_train, eval_set=[(X_train_sc,y_train)], verbose=False)
xgb_pred = xgb_best.predict(X_test_sc)
# For directional/strategy, use lag_price_1 if present; else fallback to last train price
today_ref = X_test['lag_price_1'].values if 'lag_price_1' in X_test.columns else np.array([train_df['Price'].iloc[-1]])
xgb_eval = evaluate_forecast(y_test.values, xgb_pred, today_ref)

plt.figure(figsize=(10,3))
plt.plot(test_df.index, y_test.values, 'o', label='Actual')
plt.plot(test_df.index, xgb_pred, 'x', label='XGB Pred')
plt.title('XGBoost vs Actual (last day)')
plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()

# -------------------------
# 6. LSTM (one-step ahead)
# -------------------------
print("Fitting LSTM...")
look_back = 20
scaler_lstm = MinMaxScaler(feature_range=(-1, 1))
train_price = train_df['Price'].values.reshape(-1, 1)
train_scaled = scaler_lstm.fit_transform(train_price)

# Build sequences
X_seq, y_seq = [], []
for i in range(look_back, len(train_scaled)):
    X_seq.append(train_scaled[i - look_back:i, 0])
    y_seq.append(train_scaled[i, 0])  # predict current from previous look_back
X_seq = np.array(X_seq)  # (n_samples, look_back)
y_seq = np.array(y_seq).reshape(-1, 1)

# Convert to tensors of shape (seq_len, 1, input_size)
X_seq_tensors = [torch.tensor(x.reshape(look_back, 1, 1), dtype=torch.float32) for x in X_seq]
y_seq_tensors = [torch.tensor(y, dtype=torch.float32) for y in y_seq]

lstm_model = LSTM(input_size=1, hidden_layer_size=50, output_size=1)
criterion = nn.MSELoss()
optimizer = optim.Adam(lstm_model.parameters(), lr=0.001)

epochs = 60
for epoch in range(epochs):
    total_loss = 0.0
    lstm_model.train()
    for seq_t, target_t in zip(X_seq_tensors, y_seq_tensors):
        optimizer.zero_grad()
        yhat = lstm_model(seq_t)
        loss = criterion(yhat, target_t)
        loss.backward()
        optimizer.step()
        total_loss += float(loss.item())
    if (epoch+1) % 20 == 0:
        print(f"Epoch {epoch+1}/{epochs} - loss: {total_loss/len(X_seq_tensors):.6f}")

# Predict next day using last look_back prices from FULL df (train + last day context)
lstm_model.eval()
last_seq = df['Price'].values[-look_back:].reshape(-1, 1)
last_seq_scaled = scaler_lstm.transform(last_seq)
last_seq_tensor = torch.tensor(last_seq_scaled.reshape(look_back, 1, 1), dtype=torch.float32)
with torch.no_grad():
    lstm_pred_scaled = lstm_model(last_seq_tensor).numpy().reshape(-1, 1)
lstm_pred = scaler_lstm.inverse_transform(lstm_pred_scaled).flatten()

lstm_eval = evaluate_forecast(test_df['Price'].values, lstm_pred, np.array([train_df['Price'].iloc[-1]]))

plt.figure(figsize=(10,3))
plt.plot(train_df.index, train_df['Price'], label='Train')
plt.plot(test_df.index, test_df['Price'], 'o', label='Test')
plt.plot(test_df.index, lstm_pred, 'x', label='LSTM Forecast')
plt.title('LSTM vs Actual (last day)')
plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()
 
lstm_preds_train_vals = []
lstm_preds_train_idx = []
for i in range(look_back, len(train_df)):
    window_prices = train_df['Price'].values[i - look_back:i].reshape(-1, 1)
    wp_scaled = scaler_lstm.transform(window_prices)
    window_tensor = torch.tensor(wp_scaled.reshape(look_back, 1, 1), dtype=torch.float32)
    with torch.no_grad():
        pred_scaled = lstm_model(window_tensor).numpy().reshape(-1, 1)
    pred_val = scaler_lstm.inverse_transform(pred_scaled).flatten()[0]
    lstm_preds_train_vals.append(pred_val)
    lstm_preds_train_idx.append(train_df.index[i])  # prediction for index i (next after the window)

lstm_preds_train = pd.Series(lstm_preds_train_vals, index=lstm_preds_train_idx)

# Align train features (drop first look_back rows so LSTM preds exist)
X_train_h = X_train.copy().loc[lstm_preds_train.index].copy()
y_train_h = y_train.loc[lstm_preds_train.index].copy()
X_train_h['LSTM_pred'] = lstm_preds_train

# Test LSTM pred (computed above as lstm_pred[0] for the last day)
X_test_h = X_test.copy()
X_test_h['LSTM_pred'] = lstm_pred[0]

# Re-scale and fit hybrid XGB
scaler_h = StandardScaler()
X_train_h_sc = scaler_h.fit_transform(X_train_h)
X_test_h_sc = scaler_h.transform(X_test_h)

hybrid_xgb = xgb.XGBRegressor(objective='reg:squarederror',
                              n_estimators=xgb_best.get_params()['n_estimators'],
                              max_depth=xgb_best.get_params()['max_depth'],
                              learning_rate=xgb_best.get_params()['learning_rate'],
                              subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)
hybrid_xgb.fit(X_train_h_sc, y_train_h, eval_set=[(X_train_h_sc,y_train_h)], verbose=False)
hybrid_pred = hybrid_xgb.predict(X_test_h_sc)

# directional baseline for hybrid: use lag_price_1 if present
today_ref_h = X_test_h['lag_price_1'].values if 'lag_price_1' in X_test_h.columns else np.array([train_df['Price'].iloc[-1]])
hybrid_eval = evaluate_forecast(y_test.values, hybrid_pred, today_ref_h)

plt.figure(figsize=(10,3))
plt.plot(test_df.index, y_test.values, 'o', label='Actual')
plt.plot(test_df.index, hybrid_pred, 'x', label='Hybrid Pred')
plt.title('Hybrid LSTM+XGB vs Actual (last day)')
plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()

# -------------------------
# 8. Summary table
# -------------------------
summary = pd.DataFrame({'Model': ['ARIMA', 'Prophet', 'XGBoost', 'LSTM', 'Hybrid LSTM+XGBoost'],
    'MAE': [arima_eval['MAE'], prophet_eval['MAE'], xgb_eval['MAE'], lstm_eval['MAE'], hybrid_eval['MAE']],
    'RMSE': [arima_eval['RMSE'], prophet_eval['RMSE'], xgb_eval['RMSE'], lstm_eval['RMSE'], hybrid_eval['RMSE']],
    'DirAcc': [arima_eval['DirAcc'], prophet_eval['DirAcc'], xgb_eval['DirAcc'], lstm_eval['DirAcc'], hybrid_eval['DirAcc']],
    'CumReturn': [arima_eval['CumReturn'], prophet_eval['CumReturn'], xgb_eval['CumReturn'], lstm_eval['CumReturn'], hybrid_eval['CumReturn']],
    'Sharpe': [arima_eval['Sharpe'], prophet_eval['Sharpe'], xgb_eval['Sharpe'], lstm_eval['Sharpe'], hybrid_eval['Sharpe']]
})
print("\nModel comparison on last day:")
print(summary)

# Save artifacts
summary.to_csv("btc_model_comparison_last_day.csv", index=False)
out = test_df[['Price']].copy()
out['ARIMA'] = arima_forecast.values
out['Prophet'] = prophet_pred
out['XGB'] = xgb_pred
out['LSTM'] = lstm_pred
out['Hybrid'] = hybrid_pred
out.to_csv("btc_last_day_predictions.csv")
print("\nSaved: btc_model_comparison_last_day.csv, btc_last_day_predictions.csv")
