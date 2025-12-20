"""Welcome email template."""
from typing import Dict, Any, Tuple


def render_welcome_email(user: Dict[str, Any]) -> Tuple[str, str]:
    """
    Render welcome email for new users.

    Args:
        user: User data

    Returns:
        Tuple of (html_body, text_body)
    """
    username = user.get('github_login', 'there')

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to CICosts</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 50px 40px; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0 0 16px; color: #ffffff; font-size: 32px; font-weight: 700;">Welcome to CICosts! 🎉</h1>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.9); font-size: 16px;">Your CI/CD cost intelligence platform</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 24px; color: #1f2937; font-size: 18px; font-weight: 600;">
                                Hi {username},
                            </p>

                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Thanks for signing up! We're excited to help you gain visibility into your GitHub Actions costs and optimize your CI/CD spending.
                            </p>

                            <!-- Getting Started -->
                            <h2 style="color: #1f2937; font-size: 22px; margin: 32px 0 20px; font-weight: 700;">🚀 Getting Started</h2>

                            <div style="margin-bottom: 20px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="padding: 20px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid #667eea;">
                                            <div style="color: #667eea; font-weight: 700; font-size: 18px; margin-bottom: 8px;">1. Install the GitHub App</div>
                                            <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                                                Connect CICosts to your GitHub organization to start tracking workflow costs.
                                            </p>
                                            <a href="https://cicosts.dev/install" style="display: inline-block; margin-top: 12px; color: #667eea; text-decoration: none; font-weight: 600;">Install App →</a>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <div style="margin-bottom: 20px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="padding: 20px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid #10b981;">
                                            <div style="color: #10b981; font-weight: 700; font-size: 18px; margin-bottom: 8px;">2. View Your Dashboard</div>
                                            <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                                                See real-time cost analytics, workflow breakdowns, and optimization opportunities.
                                            </p>
                                            <a href="https://cicosts.dev/dashboard" style="display: inline-block; margin-top: 12px; color: #10b981; text-decoration: none; font-weight: 600;">Go to Dashboard →</a>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <div style="margin-bottom: 20px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="padding: 20px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid #f59e0b;">
                                            <div style="color: #f59e0b; font-weight: 700; font-size: 18px; margin-bottom: 8px;">3. Set Up Alerts</div>
                                            <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                                                Get notified when costs exceed your thresholds so you can take action quickly.
                                            </p>
                                            <a href="https://cicosts.dev/alerts" style="display: inline-block; margin-top: 12px; color: #f59e0b; text-decoration: none; font-weight: 600;">Configure Alerts →</a>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- Features -->
                            <h2 style="color: #1f2937; font-size: 22px; margin: 40px 0 20px; font-weight: 700;">✨ Key Features</h2>

                            <ul style="margin: 0 0 32px; padding-left: 20px; color: #4b5563; font-size: 15px; line-height: 1.8;">
                                <li><strong>Real-time Cost Tracking</strong> - Monitor GitHub Actions costs as they happen</li>
                                <li><strong>Workflow Analytics</strong> - Identify your most expensive workflows and jobs</li>
                                <li><strong>Cost Alerts</strong> - Get notified when spending exceeds thresholds</li>
                                <li><strong>Weekly Digests</strong> - Receive cost summaries delivered to your inbox</li>
                                <li><strong>Optimization Insights</strong> - Get actionable recommendations to reduce costs</li>
                            </ul>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 32px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://cicosts.dev/dashboard" style="display: inline-block; padding: 16px 40px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">Get Started Now</a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Help Section -->
                            <div style="margin-top: 40px; padding: 24px; background-color: #f0f9ff; border-radius: 8px; border: 1px solid #bfdbfe;">
                                <h3 style="margin: 0 0 12px; color: #1e40af; font-size: 16px; font-weight: 700;">Need Help?</h3>
                                <p style="margin: 0; color: #1e40af; font-size: 14px; line-height: 1.6;">
                                    Check out our <a href="https://cicosts.dev/docs" style="color: #1e40af; text-decoration: underline;">documentation</a> or reach out to our support team anytime. We're here to help!
                                </p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 12px; color: #1f2937; font-size: 14px; font-weight: 600;">Happy cost tracking! 🎯</p>
                            <p style="margin: 0; color: #6b7280; font-size: 13px; line-height: 1.5;">
                                <strong>The CICosts Team</strong><br>
                                Questions? Just reply to this email.
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
WELCOME TO CICOSTS!

Hi {username},

Thanks for signing up! We're excited to help you gain visibility into your GitHub Actions costs and optimize your CI/CD spending.

GETTING STARTED

1. Install the GitHub App
   Connect CICosts to your GitHub organization to start tracking workflow costs.
   https://cicosts.dev/install

2. View Your Dashboard
   See real-time cost analytics, workflow breakdowns, and optimization opportunities.
   https://cicosts.dev/dashboard

3. Set Up Alerts
   Get notified when costs exceed your thresholds so you can take action quickly.
   https://cicosts.dev/alerts

KEY FEATURES

- Real-time Cost Tracking - Monitor GitHub Actions costs as they happen
- Workflow Analytics - Identify your most expensive workflows and jobs
- Cost Alerts - Get notified when spending exceeds thresholds
- Weekly Digests - Receive cost summaries delivered to your inbox
- Optimization Insights - Get actionable recommendations to reduce costs

Get started now: https://cicosts.dev/dashboard

NEED HELP?

Check out our documentation: https://cicosts.dev/docs
Or reach out to our support team anytime. We're here to help!

Happy cost tracking!

--
The CICosts Team
Questions? Just reply to this email.
"""

    return html_body, text_body
