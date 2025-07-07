from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict

class RewardAnalyzer:
    def __init__(self):
        self.reward_categories = {
            'cashback': {
                'Food & Dining': 0.03,
                'Transportation': 0.02,
                'Shopping': 0.01,
                'default': 0.01
            },
            'points': {
                'Food & Dining': 3,
                'Transportation': 2,
                'Shopping': 1,
                'default': 1
            },
            'miles': {
                'Food & Dining': 2,
                'Transportation': 3,
                'Shopping': 1,
                'default': 1
            }
        }
        
        self.interest_tiers = {
            'promotional': {'rate': 0.0, 'period_months': 12},
            'standard': {'rate': 0.1999, 'period_months': None},
            'penalty': {'rate': 0.2999, 'period_months': None}
        }
    
    def analyze_rewards(self, transactions: List[Dict], credit_card_info: Dict) -> Dict:
        if not transactions:
            return {}
        
        reward_type = credit_card_info.get('reward_type', 'cashback')
        reward_rates = self.reward_categories.get(reward_type, self.reward_categories['cashback'])
        
        analysis = {
            'total_rewards_earned': 0,
            'rewards_by_category': {},
            'monthly_rewards': {},
            'potential_rewards': {},
            'recommendations': []
        }
        
        category_totals = defaultdict(float)
        monthly_totals = defaultdict(float)
        
        for transaction in transactions:
            amount = transaction.get('amount', 0)
            category = transaction.get('category', 'Other')
            date = transaction.get('date', datetime.now())
            
            if isinstance(date, str):
                date = pd.to_datetime(date)
            
            month_key = date.strftime('%Y-%m')
            
            category_totals[category] += amount
            monthly_totals[month_key] += amount
        
        for category, total_amount in category_totals.items():
            reward_rate = reward_rates.get(category, reward_rates['default'])
            rewards_earned = total_amount * reward_rate
            
            analysis['total_rewards_earned'] += rewards_earned
            analysis['rewards_by_category'][category] = {
                'spending': total_amount,
                'reward_rate': reward_rate,
                'rewards_earned': rewards_earned
            }
        
        for month, total_amount in monthly_totals.items():
            avg_reward_rate = analysis['total_rewards_earned'] / sum(category_totals.values()) if sum(category_totals.values()) > 0 else 0
            analysis['monthly_rewards'][month] = {
                'spending': total_amount,
                'estimated_rewards': total_amount * avg_reward_rate
            }
        
        analysis['potential_rewards'] = self._calculate_potential_rewards(category_totals, reward_rates)
        analysis['recommendations'] = self._generate_reward_recommendations(analysis)
        
        return analysis
    
    def _calculate_potential_rewards(self, category_totals: Dict, reward_rates: Dict) -> Dict:
        potential = {}
        
        best_rates = {
            'Food & Dining': 0.05,
            'Transportation': 0.04,
            'Shopping': 0.03,
            'default': 0.02
        }
        
        for category, total_amount in category_totals.items():
            current_rate = reward_rates.get(category, reward_rates['default'])
            best_rate = best_rates.get(category, best_rates['default'])
            
            current_rewards = total_amount * current_rate
            potential_rewards = total_amount * best_rate
            
            potential[category] = {
                'current_rewards': current_rewards,
                'potential_rewards': potential_rewards,
                'additional_rewards': potential_rewards - current_rewards,
                'improvement_rate': best_rate - current_rate
            }
        
        return potential
    
    def _generate_reward_recommendations(self, analysis: Dict) -> List[str]:
        recommendations = []
        
        potential_rewards = analysis.get('potential_rewards', {})
        
        for category, data in potential_rewards.items():
            if data['additional_rewards'] > 50:
                recommendations.append(
                    f"Consider a card with better {category} rewards - potential additional ${data['additional_rewards']:.2f}/year"
                )
        
        category_spending = analysis.get('rewards_by_category', {})
        top_categories = sorted(category_spending.items(), key=lambda x: x[1]['spending'], reverse=True)[:3]
        
        for category, data in top_categories:
            if data['reward_rate'] < 0.02:
                recommendations.append(
                    f"Your top spending category '{category}' has low rewards - consider optimizing"
                )
        
        return recommendations
    
    def calculate_interest_charges(self, credit_card_info: Dict, payment_history: List[Dict]) -> Dict:
        analysis = {
            'current_balance': credit_card_info.get('current_balance', 0),
            'minimum_payment': credit_card_info.get('minimum_payment', 0),
            'apr': credit_card_info.get('apr', 0.1999),
            'monthly_interest_rate': credit_card_info.get('apr', 0.1999) / 12,
            'projected_payoff': {},
            'interest_scenarios': {}
        }
        
        balance = analysis['current_balance']
        min_payment = analysis['minimum_payment']
        monthly_rate = analysis['monthly_interest_rate']
        
        scenarios = {
            'minimum_payment': min_payment,
            'double_minimum': min_payment * 2,
            'fixed_200': 200,
            'fixed_500': 500
        }
        
        for scenario_name, payment_amount in scenarios.items():
            if payment_amount <= 0:
                continue
            
            months_to_payoff = 0
            total_interest = 0
            remaining_balance = balance
            
            while remaining_balance > 0 and months_to_payoff < 600:
                interest_charge = remaining_balance * monthly_rate
                principal_payment = payment_amount - interest_charge
                
                if principal_payment <= 0:
                    months_to_payoff = 600
                    total_interest = float('inf')
                    break
                
                remaining_balance -= principal_payment
                total_interest += interest_charge
                months_to_payoff += 1
                
                if remaining_balance < 0:
                    remaining_balance = 0
            
            analysis['interest_scenarios'][scenario_name] = {
                'monthly_payment': payment_amount,
                'months_to_payoff': months_to_payoff,
                'total_interest': total_interest,
                'total_paid': balance + total_interest
            }
        
        return analysis
    
    def generate_spending_insights(self, transactions: List[Dict]) -> Dict:
        if not transactions:
            return {}
        
        insights = {
            'spending_trends': {},
            'category_patterns': {},
            'monthly_analysis': {},
            'recommendations': []
        }
        
        df = pd.DataFrame(transactions)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df['month'] = df['date'].dt.to_period('M')
            df['day_of_week'] = df['date'].dt.day_name()
            df['hour'] = df['date'].dt.hour
        
        monthly_spending = df.groupby('month')['amount'].sum().to_dict()
        insights['monthly_analysis'] = {str(k): v for k, v in monthly_spending.items()}
        
        category_spending = df.groupby('category')['amount'].agg(['sum', 'mean', 'count']).to_dict('index')
        insights['category_patterns'] = category_spending
        
        if len(monthly_spending) > 1:
            spending_values = list(monthly_spending.values())
            avg_spending = sum(spending_values) / len(spending_values)
            
            if spending_values[-1] > avg_spending * 1.2:
                insights['recommendations'].append("Your spending increased significantly last month - consider reviewing your budget")
            
            if spending_values[-1] < avg_spending * 0.8:
                insights['recommendations'].append("Great job reducing spending last month!")
        
        high_value_transactions = df[df['amount'] > df['amount'].quantile(0.9)]
        if len(high_value_transactions) > 0:
            insights['high_value_transactions'] = {
                'count': len(high_value_transactions),
                'total_amount': high_value_transactions['amount'].sum(),
                'avg_amount': high_value_transactions['amount'].mean()
            }
        
        return insights
    
    def calculate_credit_utilization(self, credit_card_info: Dict) -> Dict:
        current_balance = credit_card_info.get('current_balance', 0)
        credit_limit = credit_card_info.get('credit_limit', 0)
        
        if credit_limit == 0:
            return {'utilization_rate': 0, 'status': 'Unknown - no credit limit provided'}
        
        utilization_rate = (current_balance / credit_limit) * 100
        
        analysis = {
            'utilization_rate': utilization_rate,
            'current_balance': current_balance,
            'credit_limit': credit_limit,
            'available_credit': credit_limit - current_balance,
            'status': '',
            'recommendations': []
        }
        
        if utilization_rate <= 10:
            analysis['status'] = 'Excellent'
            analysis['recommendations'].append("Excellent credit utilization - keep it up!")
        elif utilization_rate <= 30:
            analysis['status'] = 'Good'
            analysis['recommendations'].append("Good credit utilization - try to keep it below 10% for optimal credit score")
        elif utilization_rate <= 50:
            analysis['status'] = 'Fair'
            analysis['recommendations'].append("Consider paying down your balance to improve credit score")
        else:
            analysis['status'] = 'Poor'
            analysis['recommendations'].append("High credit utilization - prioritize paying down this balance")
        
        return analysis
    
    def generate_comprehensive_report(self, transactions: List[Dict], credit_card_info: Dict, payment_history: List[Dict] = None) -> Dict:
        report = {
            'summary': {
                'total_transactions': len(transactions),
                'total_spending': sum(t.get('amount', 0) for t in transactions),
                'report_date': datetime.now().isoformat()
            },
            'rewards_analysis': self.analyze_rewards(transactions, credit_card_info),
            'spending_insights': self.generate_spending_insights(transactions),
            'credit_utilization': self.calculate_credit_utilization(credit_card_info)
        }
        
        if payment_history:
            report['interest_analysis'] = self.calculate_interest_charges(credit_card_info, payment_history)
        
        return report