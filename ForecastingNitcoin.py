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


def compute_technical_indicators(df):
    """Add some common technical indicators to df (in-place)"""
    # price series must be numeric
    price = df['Price']
    high = df.get('High', price)
    low = df.get('Low', price)
    close = price
    volume = df.get('Volume', None)

    df['SMA_10'] = ta.trend.sma_indicator(close, window=10)
    df['SMA_50'] = ta.trend.sma_indicator(close, window=50)
    df['RSI_14'] = ta.momentum.rsi(close, window=14)
    # Bollinger bands (pandas-ta/ta returns single series functions, so compute components)
    df['BB_middle'] = ta.volatility.bollinger_mavg(close, window=20)
    df['BB_upper'] = ta.volatility.bollinger_hband(close, window=20)
    df['BB_lower'] = ta.volatility.bollinger_lband(close, window=20)
    # ATR
    df['ATR_14'] = ta.volatility.average_true_range(high, low, close, window=14)
    # MACD
    df['MACD'] = ta.trend.macd(close)
    df['MACD_signal'] = ta.trend.macd_signal(close)
    df['MACD_diff'] = ta.trend.macd_diff(close)

    # returns
    df['ret'] = df['Price'].pct_change()
    df['logret'] = np.log(df['Price']).diff()

    # lags (simple)
    n_lags = 5
    for lag in range(1, n_lags + 1):
        df[f'lag_price_{lag}'] = df['Price'].shift(lag)
        df[f'lag_ret_{lag}'] = df['ret'].shift(lag)

    return df

def evaluate_forecast(y_true, y_pred, today_price):
    """Return dict with MAE, RMSE, directional accuracy, strategy cum return, and approx Sharpe."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    # Directional accuracy: sign(next - today) correctness
    direction_actual = np.sign(y_true - today_price)
    direction_pred = np.sign(y_pred - today_price)
    dir_acc = np.mean(direction_actual == direction_pred)

    # Strategy: long-only when predicted > today_price, else flat
    pred_signal = (y_pred > today_price).astype(int)
    actual_returns = (y_true - today_price) / today_price
    strategy_returns = pred_signal * actual_returns

    # Cumulative return
    cum_return = (1 + pd.Series(strategy_returns)).cumprod().iloc[-1] - 1
    # Approx annualized Sharpe (assume daily returns, 252 trading days)
    if np.std(strategy_returns) > 0:
        sharpe = np.mean(strategy_returns) / (np.std(strategy_returns) + 1e-9) * np.sqrt(252)
    else:
        sharpe = np.nan

    return {
        'MAE': mae,
        'RMSE': rmse,
        'DirAcc': dir_acc,
        'CumReturn': cum_return,
        'Sharpe': sharpe
    }

# -------------------------
# 0. Load and clean
# -------------------------
DATA_PATH = "Bitcoin Historical Data.csv"   # adjust path as needed

df = pd.read_csv(DATA_PATH)
# Clean commas and types
for col in ['Price', 'High', 'Low', 'Volume']:
    if col in df.columns and df[col].dtype == object:
        df[col] = df[col].str.replace(',', '', regex=False)
        # some volumes contain '-'; convert errors to NaN
        df[col] = pd.to_numeric(df[col], errors='coerce')

# parse dates
if 'Date' in df.columns:
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=False, errors='coerce')
    df = df.dropna(subset=['Date'])
    df.set_index('Date', inplace=True)
else:
    raise ValueError("CSV must contain 'Date' column")

df.sort_index(inplace=True)
df = df[['Price', 'High', 'Low', 'Volume']] if 'Volume' in df.columns else df[['Price','High','Low']]

# -------------------------
# 1. Feature engineering
# -------------------------
compute_technical_indicators(df)
df = df.dropna().copy()   # drop rows where indicators are NaN

# 2. Train/test split (time-ordered)
<<<<<<< HEAD
# -------------------------
# Choose test_size proportion or explicit days
TEST_PROPORTION = 0.002 # last 5% as test, like your original
=======

TEST_PROPORTION = 0.05  # last 5% as test
>>>>>>> 89e66433026675eefbb7119d960c9fb582ac5f97
test_size = int(len(df) * TEST_PROPORTION)
train_df = df.iloc[:-test_size]
test_df  = df.iloc[-test_size:]
print(f"Rows - total: {len(df)}, train: {len(train_df)}, test: {len(test_df)}")

# -------------------------
# 3. ARIMA (fit on train, forecast into test)
arima_order = (2, 1, 1)
print("Fitting ARIMA...")
arima_model = ARIMA(train_df['Price'], order=arima_order)
arima_fit = arima_model.fit()
arima_forecast = arima_fit.forecast(steps=len(test_df))
arima_forecast.index = test_df.index

arima_eval = evaluate_forecast(test_df['Price'].values, arima_forecast.values, test_df['Price'].shift(1).values)
print("\nARIMA results:")
for k,v in arima_eval.items():
    print(f" {k}: {v}")

# Plot ARIMA results
plt.figure(figsize=(12,4))
#plt.plot(train_df.index, train_df['Price'], label='Train Price')
plt.plot(test_df.index, test_df['Price'], label='Test Price')
plt.plot(test_df.index, arima_forecast, label='ARIMA Forecast')
plt.title('ARIMA Forecast vs Actual')
plt.legend(); plt.grid(True)
plt.show()

# -------------------------
# 4. Prophet (train on train, forecast into test)
# -------------------------
print("Fitting Prophet...")
prophet_train = train_df.reset_index().rename(columns={'Date':'ds', 'Price':'y'}) if 'Date' in train_df.reset_index().columns else train_df.reset_index().rename(columns={'index':'ds','Price':'y'})
# Prophet expects columns 'ds' and 'y'
m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
m.fit(prophet_train[['ds','y']])

future = m.make_future_dataframe(periods=len(test_df), freq='D')
fcst = m.predict(future)
fcst = fcst.set_index('ds')
# align predictions to test index (if test index contains missing calendar days, we use reindex)
prophet_pred = fcst.reindex(test_df.index)['yhat'].values

prophet_eval = evaluate_forecast(test_df['Price'].values, prophet_pred, test_df['Price'].shift(1).values)
print("\nProphet results:")
for k,v in prophet_eval.items():
    print(f" {k}: {v}")

# Plot Prophet results
plt.figure(figsize=(12,4))
#plt.plot(train_df.index, train_df['Price'], label='Train Price')
plt.plot(test_df.index, test_df['Price'], label='Test Price')
plt.plot(test_df.index, prophet_pred, label='Prophet Forecast')
plt.title('Prophet Forecast vs Actual')
plt.legend(); plt.grid(True)
plt.show()

# -------------------------
# 5. XGBoost (supervised on lagged features -> predict next day price)
# -------------------------
print("Preparing supervised dataset for XGBoost...")
ml_df = df.copy()
ml_df['target_price'] = ml_df['Price'].shift(-1)   # predict next day price
ml_df.dropna(inplace=True)

# same test_size but aligned for supervised dataset
train_ml = ml_df.iloc[:-test_size]
test_ml  = ml_df.iloc[-test_size:]

# Feature list - ensure only existing columns are used
features = [c for c in ml_df.columns if c.startswith('lag_') or c in
            ['SMA_10','SMA_50','RSI_14','MACD','MACD_signal','ret','logret','Volume','ATR_14','BB_upper','BB_lower','BB_middle']]
features = [f for f in features if f in ml_df.columns]

X_train = train_ml[features].copy()
y_train = train_ml['target_price'].copy()
X_test  = test_ml[features].copy()
y_test  = test_ml['target_price'].copy()

# Scale numeric features (helps XGBoost a bit if features vary widely)
scaler = StandardScaler()
X_train_sc = pd.DataFrame(scaler.fit_transform(X_train), index=X_train.index, columns=X_train.columns)
X_test_sc  = pd.DataFrame(scaler.transform(X_test), index=X_test.index, columns=X_test.columns)

# Optional: quick hyperparameter tuning with TimeSeriesSplit (small grid to keep runtime reasonable)
print("Hyperparameter tuning XGBoost (small grid)...")
tscv = TimeSeriesSplit(n_splits=5)
param_grid = {
    'n_estimators': [100, 200],
    'max_depth': [3, 4],
    'learning_rate': [0.05, 0.1]
}
xgb_model = xgb.XGBRegressor(objective='reg:squarederror', verbosity=0)
grid = GridSearchCV(xgb_model, param_grid, cv=tscv, scoring='neg_mean_absolute_error', n_jobs=1)
grid.fit(X_train_sc, y_train)
print("Best params:", grid.best_params_)

# Fit final model with best params
best = grid.best_estimator_
best.fit(X_train_sc, y_train, eval_set=[(X_test_sc, y_test)], verbose=False)

# Predict
y_pred = best.predict(X_test_sc)

xgb_eval = evaluate_forecast(y_test.values, y_pred, X_test['lag_price_1'].values)
print("\nXGBoost results:")
for k,v in xgb_eval.items():
    print(f" {k}: {v}")

# Plot XGBoost results
plt.figure(figsize=(12,4))
plt.plot(test_ml.index, y_test.values, label='Actual Price')
plt.plot(test_ml.index, y_pred, label='XGBoost Predicted Price')
plt.title('XGBoost Prediction vs Actual')
plt.legend(); plt.grid(True)
plt.show()

# -------------------------
# 6. Directional accuracy and strategy returns (already in evaluate_forecast)
#
# -------------------------
# Build signals using predicted > today
today_price = X_test['lag_price_1'].values
pred_signal = (y_pred > today_price).astype(int)
actual_returns = (y_test.values - today_price) / today_price
strategy_returns = pred_signal * actual_returns

cumrets_series = (1 + pd.Series(strategy_returns, index=test_ml.index)).cumprod()
print("\nXGBoost simple strategy cumulative return over test:", cumrets_series.iloc[-1] - 1)
print("XGBoost approximate sharpe:", xgb_eval['Sharpe'])
plt.figure(figsize=(10,3))
plt.plot(cumrets_series.index, cumrets_series.values, label='XGB Strategy Cumulative (test)')
plt.title('Strategy Cumulative Return (XGBoost, long-only)')
plt.legend(); plt.grid(True)
plt.show()

# -------------------------
# 7. Optional: Walk-forward (expanding window) for XGBoost
# -------------------------
def walk_forward_xgb(df_ml, features, initial_train_size=None, retrain_every=1, params=None, scale=True):
    """
    Perform an expanding-window walk-forward forecasting for next-day price with XGBoost.
      - df_ml: supervised df with target_price column (index = dates)
      - features: list of feature column names
      - initial_train_size: number of rows in the first training window (if None uses 70%).
      - retrain_every: retrain model every N steps (1 = every day)
      - params: dict params for XGBRegressor
    Returns predictions series aligned to the dates predicted (one-step ahead).
    """
    if initial_train_size is None:
        initial_train_size = int(len(df_ml) * 0.7)

    preds = []
    pred_index = []
    if params is None:
        params = {'n_estimators':100, 'max_depth':4, 'learning_rate':0.05}

    for i in range(initial_train_size, len(df_ml)-1):
        train_slice = df_ml.iloc[:i].copy()
        test_row = df_ml.iloc[i:i+1].copy()  # we predict the target for i (which is next-day for row i-1)
        X_tr = train_slice[features]
        y_tr = train_slice['target_price']
        X_te = test_row[features]

        # optionally scale per-window
        if scale:
            scaler = StandardScaler()
            X_tr_sc = scaler.fit_transform(X_tr)
            X_te_sc = scaler.transform(X_te)
        else:
            X_tr_sc = X_tr.values
            X_te_sc = X_te.values

        model = xgb.XGBRegressor(objective='reg:squarederror', **params)
        model.fit(X_tr_sc, y_tr, verbose=False)

        yhat = model.predict(X_te_sc)[0]
        preds.append(yhat)
        pred_index.append(test_row.index[0])

    preds_series = pd.Series(preds, index=pred_index)
    return preds_series

RUN_WALK_FORWARD = False
if RUN_WALK_FORWARD:
    print("Running walk-forward XGBoost (this may take a while)...")
    ml_df_for_walk = ml_df.copy()
    wf_preds = walk_forward_xgb(ml_df_for_walk, features, initial_train_size=int(len(ml_df_for_walk)*0.7),
                                params=grid.best_params_, scale=True)
    # Align true next day prices
    true_for_wf = ml_df_for_walk.loc[wf_preds.index, 'target_price']
    wf_eval = evaluate_forecast(true_for_wf.values, wf_preds.values, ml_df_for_walk.loc[wf_preds.index, 'lag_price_1'].values)
    print("Walk-forward XGB eval:", wf_eval)

# -------------------------
# 8. Summary table
# -------------------------
summary = pd.DataFrame({
    'Model': ['ARIMA', 'Prophet', 'XGBoost'],
    'MAE': [arima_eval['MAE'], prophet_eval['MAE'], xgb_eval['MAE']],
    'RMSE': [arima_eval['RMSE'], prophet_eval['RMSE'], xgb_eval['RMSE']],
    'DirAcc': [arima_eval['DirAcc'], prophet_eval['DirAcc'], xgb_eval['DirAcc']],
    'CumReturn': [arima_eval['CumReturn'], prophet_eval['CumReturn'], xgb_eval['CumReturn']],
    'Sharpe': [arima_eval['Sharpe'], prophet_eval['Sharpe'], xgb_eval['Sharpe']]
})
print("\nModel comparison on test set:")
print(summary)

# Save predictions & metrics for later analysis
results = test_df.copy()
results['ARIMA_pred'] = arima_forecast
results['Prophet_pred'] = prophet_pred
results['XGB_pred'] = pd.Series(y_pred, index=test_ml.index).reindex(results.index)  # align
results.to_csv("btc_model_predictions_test.csv")
summary.to_csv("btc_model_comparison_summary.csv", index=False)
print("\nSaved btc_model_predictions_test.csv and btc_model_comparison_summary.csv")
