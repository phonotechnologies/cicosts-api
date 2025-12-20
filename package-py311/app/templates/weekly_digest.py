"""Weekly cost digest email template."""
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta, timezone


def render_weekly_digest(
    user: Dict[str, Any],
    org: Dict[str, Any],
    cost_summary: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Render weekly cost digest email.

    Args:
        user: User data
        org: Organization data
        cost_summary: Cost summary data

    Returns:
        Tuple of (html_body, text_body)
    """
    username = user.get('github_login', 'there')
    org_name = org.get('github_org_name', 'your organization')

    total_cost = cost_summary.get('total_cost', 0)
    previous_cost = cost_summary.get('previous_week_cost', 0)
    change_percent = cost_summary.get('change_percent', 0)
    top_workflows = cost_summary.get('top_workflows', [])
    top_repos = cost_summary.get('top_repos', [])

    # Determine trend
    trend_icon = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
    trend_color = "#ef4444" if change_percent > 10 else "#10b981" if change_percent < -10 else "#f59e0b"
    trend_text = f"{abs(change_percent):.1f}% {'increase' if change_percent > 0 else 'decrease' if change_percent < 0 else 'no change'}"

    # Week range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    week_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

    # Top workflows HTML
    workflows_html = ""
    workflows_text = ""
    if top_workflows:
        workflows_html = "<h3 style='color: #1f2937; font-size: 18px; margin: 32px 0 16px;'>Top Workflows</h3>"
        workflows_text = "\n\nTop Workflows:\n"
        for i, wf in enumerate(top_workflows[:5], 1):
            name = wf.get('name', 'Unknown')
            cost = wf.get('cost', 0)
            runs = wf.get('runs', 0)
            workflows_html += f"""
            <div style="padding: 16px; margin-bottom: 12px; background-color: #f9fafb; border-radius: 6px; border-left: 3px solid #667eea;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="color: #1f2937; font-weight: 600; font-size: 15px; margin-bottom: 4px;">{i}. {name}</div>
                        <div style="color: #6b7280; font-size: 13px;">{runs} runs</div>
                    </div>
                    <div style="color: #667eea; font-weight: 700; font-size: 18px;">${cost:.2f}</div>
                </div>
            </div>
            """
            workflows_text += f"  {i}. {name} - ${cost:.2f} ({runs} runs)\n"

    # Top repos HTML
    repos_html = ""
    repos_text = ""
    if top_repos:
        repos_html = "<h3 style='color: #1f2937; font-size: 18px; margin: 32px 0 16px;'>Top Repositories</h3>"
        repos_text = "\n\nTop Repositories:\n"
        for i, repo in enumerate(top_repos[:5], 1):
            name = repo.get('name', 'Unknown')
            cost = repo.get('cost', 0)
            repos_html += f"""
            <div style="padding: 12px 16px; margin-bottom: 8px; background-color: #f9fafb; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #1f2937; font-weight: 500;">{i}. {name}</span>
                <span style="color: #667eea; font-weight: 600;">${cost:.2f}</span>
            </div>
            """
            repos_text += f"  {i}. {name} - ${cost:.2f}\n"

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Cost Digest</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 40px 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0 0 8px; color: #ffffff; font-size: 28px; font-weight: 700;">📊 Weekly Cost Digest</h1>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.9); font-size: 15px;">{week_range}</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 32px; color: #4b5563; font-size: 16px; line-height: 1.5;">
                                Hi {username}, here's your weekly CI/CD cost summary for <strong>{org_name}</strong>.
                            </p>

                            <!-- Cost Overview -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
                                <tr>
                                    <td style="width: 50%; padding-right: 12px;">
                                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 24px; border-radius: 8px; text-align: center;">
                                            <div style="color: rgba(255, 255, 255, 0.9); font-size: 14px; margin-bottom: 8px;">This Week</div>
                                            <div style="color: #ffffff; font-size: 36px; font-weight: 700;">${total_cost:.2f}</div>
                                        </div>
                                    </td>
                                    <td style="width: 50%; padding-left: 12px;">
                                        <div style="background-color: #f9fafb; padding: 24px; border-radius: 8px; text-align: center; border: 2px solid #e5e7eb;">
                                            <div style="color: #6b7280; font-size: 14px; margin-bottom: 8px;">Last Week</div>
                                            <div style="color: #1f2937; font-size: 36px; font-weight: 700;">${previous_cost:.2f}</div>
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Trend -->
                            <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin-bottom: 32px; text-align: center; border-left: 4px solid {trend_color};">
                                <span style="font-size: 24px; margin-right: 8px;">{trend_icon}</span>
                                <span style="color: {trend_color}; font-weight: 700; font-size: 20px;">{trend_text}</span>
                                <span style="color: #6b7280; font-size: 16px;"> from last week</span>
                            </div>

                            {workflows_html}

                            {repos_html}

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 40px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://cicosts.dev/dashboard" style="display: inline-block; padding: 14px 32px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">View Full Dashboard</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 32px 0 0; color: #6b7280; font-size: 14px; line-height: 1.5; text-align: center;">
                                Want to reduce your costs? Check out our <a href="https://cicosts.dev/insights" style="color: #667eea; text-decoration: none;">cost optimization insights</a>.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #6b7280; font-size: 13px; line-height: 1.5;">
                                <strong>CICosts</strong> - CI/CD Cost Intelligence<br>
                                Don't want weekly digests? <a href="https://cicosts.dev/settings/notifications" style="color: #667eea; text-decoration: none;">Update your preferences</a>
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
WEEKLY COST DIGEST
{week_range}

Hi {username},

Here's your weekly CI/CD cost summary for {org_name}.

THIS WEEK: ${total_cost:.2f}
LAST WEEK: ${previous_cost:.2f}

{trend_icon} {trend_text} from last week
{workflows_text}{repos_text}
View full dashboard: https://cicosts.dev/dashboard

Want to reduce your costs? Check out our cost optimization insights:
https://cicosts.dev/insights

--
CICosts - CI/CD Cost Intelligence
Don't want weekly digests? Update your preferences:
https://cicosts.dev/settings/notifications
"""

    return html_body, text_body
