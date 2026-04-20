import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime, timedelta
import logging
from core.notifier import notifier

log = logging.getLogger(__name__)

class PDFReportGenerator:
    def __init__(self, db_path="said alalawi.db"):
        self.db_path = db_path
        self.reports_dir = "reports"
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)

    def _get_equity_data(self, days=7):
        """Fetches equity history for the chart."""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT total_equity, timestamp 
                FROM equity_history 
                WHERE timestamp >= datetime('now', ?) 
                ORDER BY timestamp ASC
            """
            df = pd.read_sql_query(query, conn, params=(f"-{days} days",))
            conn.close()
            return df
        except Exception as e:
            log.error(f"Error fetching equity data: {e}")
            return pd.DataFrame()

    def _get_pattern_stats(self, days=7):
        """Fetches win/loss stats per pattern."""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT pattern, 
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN outcome = -1 THEN 1 ELSE 0 END) as losses
                FROM signals 
                WHERE outcome != 0 AND created_at >= datetime('now', ?)
                GROUP BY pattern
            """
            df = pd.read_sql_query(query, conn, params=(f"-{days} days",))
            conn.close()
            return df
        except Exception as e:
            log.error(f"Error fetching pattern stats: {e}")
            return pd.DataFrame()

    def _create_chart(self, equity_df):
        """Generates the equity curve image."""
        if equity_df.empty:
            return None
        
        plt.figure(figsize=(10, 5), facecolor='#0B0E11')
        ax = plt.gca()
        ax.set_facecolor('#0B0E11')
        
        # Plot curve
        plt.plot(pd.to_datetime(equity_df['timestamp']), equity_df['total_equity'], color='#00A3FF', linewidth=2)
        plt.fill_between(pd.to_datetime(equity_df['timestamp']), equity_df['total_equity'], color='#00A3FF', alpha=0.1)
        
        plt.title("Weekly Equity Performance", color='white', fontsize=14, pad=20)
        plt.xticks(color='white', alpha=0.6)
        plt.yticks(color='white', alpha=0.6)
        plt.grid(True, alpha=0.1, color='white')
        
        for spine in ax.spines.values():
            spine.set_visible(False)
            
        chart_path = os.path.join(self.reports_dir, "temp_chart.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        return chart_path

    def generate_weekly_report(self):
        """Generates the main institution PDF report."""
        log.info("Generating Weekly Performance Report...")
        
        equity_df = self._get_equity_data()
        stats_df = self._get_pattern_stats()
        chart_path = self._create_chart(equity_df)
        
        pdf = FPDF()
        pdf.add_page()
        
        # --- Header ---
        pdf.set_fill_color(11, 14, 17)
        pdf.rect(0, 0, 210, 40, 'F')
        
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 20, "SENTINEL TECHNICAL CORE", ln=True, align='C')
        
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, f"Portfolio Performance Report: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
        
        # --- Summary Stats ---
        pdf.ln(20)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Executive Summary", ln=True)
        
        total_trades = int(stats_df['total'].sum()) if not stats_df.empty else 0
        total_wins = int(stats_df['wins'].sum()) if not stats_df.empty else 0
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(100, 10, f"Total Trades: {total_trades}")
        pdf.cell(0, 10, f"Weekly Win Rate: {win_rate:.1f}%", ln=True)
        
        # --- Chart ---
        if chart_path:
            pdf.ln(10)
            pdf.image(chart_path, x=10, w=190)
            os.remove(chart_path) # cleanup
            
        # --- Leaderboard ---
        pdf.ln(10)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Strategy Performance Leaderboard", ln=True)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 10, "Pattern", border=1)
        pdf.cell(40, 10, "Total", border=1)
        pdf.cell(40, 10, "Wins", border=1)
        pdf.cell(40, 10, "Win Rate", border=1, ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for _, row in stats_df.iterrows():
            wr = (row['wins'] / row['total'] * 100)
            pdf.cell(60, 10, str(row['pattern']), border=1)
            pdf.cell(40, 10, str(int(row['total'])), border=1)
            pdf.cell(40, 10, str(int(row['wins'])), border=1)
            pdf.cell(40, 10, f"{wr:.1f}%", border=1, ln=True)
            
        # Footer
        pdf.set_y(-20)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, "Sentinel Core - Secure Institutional Algo Flow", align='C')
        
        report_name = f"Jewel_Elite_Report_{datetime.now().strftime('%Y_%m_%d')}.pdf"
        report_path = os.path.join(self.reports_dir, report_name)
        pdf.output(report_path)
        
        # Send to Telegram
        notifier.send_document(report_path, caption=f"📊 Weekly Institutional Performance Report is ready.")
        
        return report_path

# Global instance for the scheduler
report_gen = PDFReportGenerator()

if __name__ == "__main__":
    # Manual test
    report_gen.generate_weekly_report()
