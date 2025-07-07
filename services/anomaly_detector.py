import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from datetime import datetime, timedelta
import statistics

class AnomalyDetector:
    def __init__(self):
        self.isolation_forest = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.dbscan = DBSCAN(eps=0.5, min_samples=5)
        
        self.anomaly_types = {
            'amount_outlier': 'Transaction amount significantly higher than usual',
            'frequency_anomaly': 'Unusual frequency of transactions',
            'time_anomaly': 'Transaction at unusual time',
            'location_anomaly': 'Transaction at unusual location',
            'merchant_anomaly': 'First-time merchant with large amount',
            'category_anomaly': 'Unusual spending in category',
            'velocity_anomaly': 'Multiple transactions in short time',
            'amount_pattern': 'Unusual amount pattern'
        }
    
    def detect_anomalies(self, transactions: List[Dict]) -> List[Dict]:
        if len(transactions) < 10:
            return []
        
        df = self._prepare_dataframe(transactions)
        
        anomalies = []
        
        anomalies.extend(self._detect_amount_anomalies(df))
        anomalies.extend(self._detect_frequency_anomalies(df))
        anomalies.extend(self._detect_time_anomalies(df))
        anomalies.extend(self._detect_merchant_anomalies(df))
        anomalies.extend(self._detect_category_anomalies(df))
        anomalies.extend(self._detect_velocity_anomalies(df))
        anomalies.extend(self._detect_pattern_anomalies(df))
        
        if len(df) > 20:
            anomalies.extend(self._detect_ml_anomalies(df))
        
        return self._deduplicate_anomalies(anomalies)
    
    def _prepare_dataframe(self, transactions: List[Dict]) -> pd.DataFrame:
        df_data = []
        
        for i, transaction in enumerate(transactions):
            row = {
                'id': transaction.get('id', i),
                'amount': transaction.get('amount', 0),
                'merchant': transaction.get('merchant', 'Unknown'),
                'category': transaction.get('category', 'Other'),
                'date': transaction.get('date', datetime.now()),
                'description': transaction.get('description', ''),
                'raw_text': transaction.get('raw_text', ''),
                'original_transaction': transaction
            }
            
            if isinstance(row['date'], str):
                try:
                    row['date'] = pd.to_datetime(row['date'])
                except:
                    row['date'] = datetime.now()
            
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        df['hour'] = df['date'].dt.hour
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        
        return df
    
    def _detect_amount_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        amounts = df['amount'].values
        q1 = np.percentile(amounts, 25)
        q3 = np.percentile(amounts, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 3 * iqr
        upper_bound = q3 + 3 * iqr
        
        for idx, row in df.iterrows():
            amount = row['amount']
            if amount > upper_bound or amount < lower_bound:
                anomaly_score = abs(amount - np.median(amounts)) / np.std(amounts)
                
                anomalies.append({
                    'transaction_id': row['id'],
                    'anomaly_type': 'amount_outlier',
                    'score': min(anomaly_score, 1.0),
                    'description': f'Amount ${amount:.2f} is unusual (typical range: ${q1:.2f} - ${q3:.2f})',
                    'transaction': row['original_transaction']
                })
        
        return anomalies
    
    def _detect_frequency_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        merchant_counts = df['merchant'].value_counts()
        
        for merchant, count in merchant_counts.items():
            if count >= 10:
                merchant_transactions = df[df['merchant'] == merchant]
                
                daily_counts = merchant_transactions.groupby(merchant_transactions['date'].dt.date).size()
                
                if len(daily_counts) > 1:
                    avg_daily = daily_counts.mean()
                    std_daily = daily_counts.std()
                    
                    for date, daily_count in daily_counts.items():
                        if daily_count > avg_daily + 2 * std_daily:
                            transactions_on_date = merchant_transactions[
                                merchant_transactions['date'].dt.date == date
                            ]
                            
                            for idx, row in transactions_on_date.iterrows():
                                anomalies.append({
                                    'transaction_id': row['id'],
                                    'anomaly_type': 'frequency_anomaly',
                                    'score': min((daily_count - avg_daily) / max(std_daily, 1), 1.0),
                                    'description': f'Unusual frequency: {daily_count} transactions at {merchant} on {date}',
                                    'transaction': row['original_transaction']
                                })
        
        return anomalies
    
    def _detect_time_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        hour_counts = df['hour'].value_counts()
        typical_hours = hour_counts[hour_counts >= len(df) * 0.05].index
        
        for idx, row in df.iterrows():
            hour = row['hour']
            if hour not in typical_hours:
                if hour < 6 or hour > 23:
                    anomalies.append({
                        'transaction_id': row['id'],
                        'anomaly_type': 'time_anomaly',
                        'score': 0.7,
                        'description': f'Transaction at unusual time: {hour:02d}:00',
                        'transaction': row['original_transaction']
                    })
        
        return anomalies
    
    def _detect_merchant_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        merchant_stats = df.groupby('merchant').agg({
            'amount': ['count', 'mean', 'std'],
            'date': 'min'
        }).reset_index()
        
        merchant_stats.columns = ['merchant', 'count', 'mean_amount', 'std_amount', 'first_seen']
        
        for idx, row in df.iterrows():
            merchant = row['merchant']
            amount = row['amount']
            
            merchant_info = merchant_stats[merchant_stats['merchant'] == merchant].iloc[0]
            
            if merchant_info['count'] == 1 and amount > df['amount'].quantile(0.9):
                anomalies.append({
                    'transaction_id': row['id'],
                    'anomaly_type': 'merchant_anomaly',
                    'score': 0.8,
                    'description': f'First transaction with {merchant} for large amount ${amount:.2f}',
                    'transaction': row['original_transaction']
                })
        
        return anomalies
    
    def _detect_category_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        category_stats = df.groupby('category').agg({
            'amount': ['mean', 'std', 'count']
        }).reset_index()
        
        category_stats.columns = ['category', 'mean_amount', 'std_amount', 'count']
        
        for idx, row in df.iterrows():
            category = row['category']
            amount = row['amount']
            
            if category == 'Other':
                continue
            
            category_info = category_stats[category_stats['category'] == category]
            
            if len(category_info) > 0:
                category_info = category_info.iloc[0]
                
                if category_info['count'] >= 3 and category_info['std_amount'] > 0:
                    z_score = abs(amount - category_info['mean_amount']) / category_info['std_amount']
                    
                    if z_score > 2.5:
                        anomalies.append({
                            'transaction_id': row['id'],
                            'anomaly_type': 'category_anomaly',
                            'score': min(z_score / 3, 1.0),
                            'description': f'Unusual amount ${amount:.2f} for {category} (typical: ${category_info["mean_amount"]:.2f})',
                            'transaction': row['original_transaction']
                        })
        
        return anomalies
    
    def _detect_velocity_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        df_sorted = df.sort_values('date')
        
        for i in range(1, len(df_sorted)):
            current_row = df_sorted.iloc[i]
            prev_row = df_sorted.iloc[i-1]
            
            time_diff = (current_row['date'] - prev_row['date']).total_seconds() / 60
            
            if time_diff <= 5:
                total_amount = current_row['amount'] + prev_row['amount']
                
                if total_amount > df['amount'].quantile(0.95):
                    anomalies.append({
                        'transaction_id': current_row['id'],
                        'anomaly_type': 'velocity_anomaly',
                        'score': 0.9,
                        'description': f'Multiple large transactions within {time_diff:.1f} minutes',
                        'transaction': current_row['original_transaction']
                    })
        
        return anomalies
    
    def _detect_pattern_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        amounts = df['amount'].values
        
        round_amounts = [amount for amount in amounts if amount == round(amount)]
        
        if len(round_amounts) / len(amounts) > 0.8:
            for idx, row in df.iterrows():
                amount = row['amount']
                if amount != round(amount) and amount > df['amount'].quantile(0.8):
                    anomalies.append({
                        'transaction_id': row['id'],
                        'anomaly_type': 'amount_pattern',
                        'score': 0.6,
                        'description': f'Unusual non-round amount ${amount:.2f} in pattern of round amounts',
                        'transaction': row['original_transaction']
                    })
        
        return anomalies
    
    def _detect_ml_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        anomalies = []
        
        try:
            features = df[['amount', 'hour', 'day_of_week', 'day_of_month', 'month']].copy()
            
            merchant_encoded = pd.get_dummies(df['merchant'], prefix='merchant')
            category_encoded = pd.get_dummies(df['category'], prefix='category')
            
            features = pd.concat([features, merchant_encoded, category_encoded], axis=1)
            
            features_scaled = self.scaler.fit_transform(features)
            
            predictions = self.isolation_forest.fit_predict(features_scaled)
            anomaly_scores = self.isolation_forest.score_samples(features_scaled)
            
            for i, (prediction, score) in enumerate(zip(predictions, anomaly_scores)):
                if prediction == -1:
                    row = df.iloc[i]
                    anomalies.append({
                        'transaction_id': row['id'],
                        'anomaly_type': 'ml_anomaly',
                        'score': abs(score),
                        'description': f'Machine learning detected anomaly (score: {score:.3f})',
                        'transaction': row['original_transaction']
                    })
        
        except Exception as e:
            print(f"ML anomaly detection failed: {e}")
        
        return anomalies
    
    def _deduplicate_anomalies(self, anomalies: List[Dict]) -> List[Dict]:
        seen_transactions = set()
        deduplicated = []
        
        sorted_anomalies = sorted(anomalies, key=lambda x: x['score'], reverse=True)
        
        for anomaly in sorted_anomalies:
            transaction_id = anomaly['transaction_id']
            
            if transaction_id not in seen_transactions:
                seen_transactions.add(transaction_id)
                deduplicated.append(anomaly)
        
        return deduplicated
    
    def get_anomaly_summary(self, anomalies: List[Dict]) -> Dict:
        if not anomalies:
            return {'total_anomalies': 0, 'by_type': {}, 'avg_score': 0}
        
        summary = {
            'total_anomalies': len(anomalies),
            'by_type': {},
            'avg_score': sum(a['score'] for a in anomalies) / len(anomalies),
            'high_risk_count': sum(1 for a in anomalies if a['score'] > 0.8),
            'medium_risk_count': sum(1 for a in anomalies if 0.5 <= a['score'] <= 0.8),
            'low_risk_count': sum(1 for a in anomalies if a['score'] < 0.5)
        }
        
        for anomaly in anomalies:
            anomaly_type = anomaly['anomaly_type']
            if anomaly_type not in summary['by_type']:
                summary['by_type'][anomaly_type] = 0
            summary['by_type'][anomaly_type] += 1
        
        return summary