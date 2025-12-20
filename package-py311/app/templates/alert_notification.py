"""Alert notification email template."""
from typing import Dict, Any, Tuple
from datetime import datetime, timezone


def render_alert_email(alert: Dict[str, Any], trigger: Dict[str, Any]) -> Tuple[str, str]:
    """
    Render alert notification email.

    Args:
        alert: Alert configuration
        trigger: Trigger event data

    Returns:
        Tuple of (html_body, text_body)
    """
    current_cost = trigger.get('current_cost', 0)
    threshold = alert.get('threshold', 0)
    alert_name = alert.get('name', 'Cost Alert')
    period = alert.get('period', 'daily')
    breakdown = trigger.get('breakdown', [])

    # Generate breakdown HTML
    breakdown_html = ""
    breakdown_text = ""
    if breakdown:
        breakdown_html = "<h3 style='color: #1f2937; font-size: 16px; margin: 24px 0 12px;'>Cost Breakdown</h3><ul style='list-style: none; padding: 0;'>"
        breakdown_text = "\n\nCost Breakdown:\n"
        for item in breakdown[:5]:  # Top 5 items
            name = item.get('name', 'Unknown')
            cost = item.get('cost', 0)
            breakdown_html += f"<li style='padding: 8px 0; border-bottom: 1px solid #e5e7eb;'><span style='font-weight: 600;'>{name}</span>: <span style='color: #ef4444;'>${cost:.2f}</span></li>"
            breakdown_text += f"  - {name}: ${cost:.2f}\n"
        breakdown_html += "</ul>"

    # Get current UTC time
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cost Alert Triggered</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 40px 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">⚠️ Cost Alert Triggered</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.5;">
                                Your <strong>{alert_name}</strong> alert has been triggered.
                            </p>

                            <!-- Alert Details -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fef2f2; border-left: 4px solid #ef4444; border-radius: 4px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <div style="margin-bottom: 12px;">
                                            <span style="color: #6b7280; font-size: 14px;">Current Cost</span>
                                            <h2 style="margin: 4px 0 0; color: #ef4444; font-size: 32px; font-weight: 700;">${current_cost:.2f}</h2>
                                        </div>
                                        <div style="color: #6b7280; font-size: 14px;">
                                            Threshold: <strong style="color: #1f2937;">${threshold:.2f}</strong> ({period})
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            {breakdown_html}

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 32px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://cicosts.dev/dashboard" style="display: inline-block; padding: 14px 32px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">View Dashboard</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 32px 0 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                                This alert was triggered at {current_time}. You can manage your alert settings in the CICosts dashboard.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #6b7280; font-size: 13px; line-height: 1.5;">
                                <strong>CICosts</strong> - CI/CD Cost Intelligence<br>
                                Questions? Reply to this email or visit our <a href="https://cicosts.dev/docs" style="color: #667eea; text-decoration: none;">documentation</a>.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    text_body = f"""
COST ALERT TRIGGERED

Your {alert_name} alert has been triggered.

Current Cost: ${current_cost:.2f}
Threshold: ${threshold:.2f} ({period})
{breakdown_text}
View your dashboard: https://cicosts.dev/dashboard

This alert was triggered at {current_time}.

--
CICosts - CI/CD Cost Intelligence
Questions? Reply to this email or visit https://cicosts.dev/docs
"""

    return html_body, text_body
