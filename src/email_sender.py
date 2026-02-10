"""Email sender for house listing notifications."""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from financials import (
    calculate_down_payment,
    calculate_total_monthly,
    get_assumptions_text,
)

# GitHub repo for favorite links
GITHUB_REPO = "toxicapplejuice/austin-house-hunter"


class EmailSender:
    """Send listing notifications via Gmail SMTP."""

    def __init__(
        self,
        gmail_address: str | None = None,
        gmail_app_password: str | None = None,
    ):
        self.gmail_address = gmail_address or os.environ.get("GMAIL_ADDRESS")
        self.gmail_app_password = gmail_app_password or os.environ.get(
            "GMAIL_APP_PASSWORD"
        )

        if not self.gmail_address or not self.gmail_app_password:
            raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD are required")

    def send_listings(
        self,
        recipient: str,
        new_listings: list[dict[str, Any]],
        favorites: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Send an email with house listings in table format.

        Args:
            recipient: Email address to send to
            new_listings: List of new listing dictionaries (top 5)
            favorites: List of favorited listing dictionaries

        Returns:
            True if email sent successfully
        """
        favorites = favorites or []
        date_str = datetime.now().strftime("%b %d")

        if not new_listings and not favorites:
            subject = f"🏠 Austin Houses - No New Matches ({date_str})"
        else:
            subject = f"🏠 Austin Houses - {len(new_listings)} New Matches ({date_str})"

        html_content = self._build_html(new_listings, favorites)
        text_content = self._build_text(new_listings, favorites)

        return self._send_email(recipient, subject, html_content, text_content)

    def _build_listing_row(self, listing: dict[str, Any], show_favorite_link: bool = True) -> str:
        """Build a single table row for a listing."""
        name = listing.get("name") or listing.get("address") or "Unknown"
        if len(name) > 30:
            name = name[:27] + "..."

        beds = listing.get("beds") or "?"
        baths = listing.get("baths") or "?"
        beds_baths = f"{beds} bd / {baths} ba"

        distance = listing.get("distance")
        distance_str = f"{distance:.1f} mi" if distance else "N/A"

        price = listing.get("price") or 0
        price_str = f"${price:,.0f}" if price else "N/A"

        down = calculate_down_payment(price) if price else 0
        down_str = f"${down:,.0f}" if down else "N/A"

        monthly = calculate_total_monthly(price) if price else 0
        monthly_str = f"${monthly:,.0f}/mo" if monthly else "N/A"

        zillow_url = listing.get("zillow_url") or "#"
        zpid = listing.get("zpid") or ""

        # Favorite link creates a GitHub issue
        favorite_url = f"https://github.com/{GITHUB_REPO}/issues/new?title=FAVORITE:%20{zpid}&body=Favoriting%20property%20{zpid}&labels=favorite"

        favorite_cell = ""
        if show_favorite_link:
            favorite_cell = f'<td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><a href="{favorite_url}" style="background-color: #ffd700; color: #333; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;">⭐ Favorite</a></td>'

        return f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;"><a href="{zillow_url}" style="color: #1a73e8; text-decoration: none;">{name}</a></td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">{beds_baths}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">{distance_str}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: bold;">{price_str}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">{down_str}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0;">{monthly_str}</td>
            {favorite_cell}
        </tr>
        """

    def _build_html(
        self,
        new_listings: list[dict[str, Any]],
        favorites: list[dict[str, Any]],
    ) -> str:
        """Build HTML email content with tables."""

        # Favorites section
        favorites_html = ""
        if favorites:
            favorites_rows = "".join(
                self._build_listing_row(l, show_favorite_link=False) for l in favorites
            )
            favorites_html = f"""
            <div style="margin-bottom: 30px;">
                <h2 style="color: #333; border-bottom: 2px solid #ffd700; padding-bottom: 10px;">
                    ⭐ YOUR FAVORITES ({len(favorites)} saved)
                </h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Name</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Beds/Baths</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Distance</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Price</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Down (20%)</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Est. Monthly</th>
                        </tr>
                    </thead>
                    <tbody>
                        {favorites_rows}
                    </tbody>
                </table>
            </div>
            """

        # New listings section
        new_listings_html = ""
        if new_listings:
            new_rows = "".join(
                self._build_listing_row(l, show_favorite_link=True) for l in new_listings
            )
            new_listings_html = f"""
            <div style="margin-bottom: 30px;">
                <h2 style="color: #333; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
                    🆕 NEW LISTINGS (Top {len(new_listings)})
                </h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Name</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Beds/Baths</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Distance</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Price</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Down (20%)</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Est. Monthly</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {new_rows}
                    </tbody>
                </table>
            </div>
            """
        else:
            new_listings_html = """
            <div style="margin-bottom: 30px; padding: 20px; background-color: #f9f9f9; border-radius: 8px;">
                <p style="color: #666; margin: 0;">No new listings matching your criteria today.</p>
            </div>
            """

        # Assumptions section
        assumptions = get_assumptions_text().replace("\n", "<br>")

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 900px; margin: 0 auto; background-color: #fafafa;">
            <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                {favorites_html}
                {new_listings_html}

                <div style="margin-top: 30px; padding: 20px; background-color: #f5f5f5; border-radius: 8px;">
                    <h3 style="color: #666; margin-top: 0;">📊 Assumptions</h3>
                    <p style="color: #888; font-size: 13px; line-height: 1.8; margin: 0;">
                        {assumptions}
                    </p>
                </div>

                <p style="color: #aaa; font-size: 11px; margin-top: 30px; text-align: center;">
                    Austin House Hunter • <a href="https://github.com/{GITHUB_REPO}" style="color: #aaa;">View on GitHub</a>
                </p>
            </div>
        </body>
        </html>
        """

    def _build_text(
        self,
        new_listings: list[dict[str, Any]],
        favorites: list[dict[str, Any]],
    ) -> str:
        """Build plain text email content."""
        lines = []

        if favorites:
            lines.append(f"⭐ YOUR FAVORITES ({len(favorites)} saved)")
            lines.append("=" * 50)
            for listing in favorites:
                name = listing.get("name") or listing.get("address") or "Unknown"
                price = listing.get("price") or 0
                lines.append(f"• {name} - ${price:,.0f}")
            lines.append("")

        if new_listings:
            lines.append(f"🆕 NEW LISTINGS (Top {len(new_listings)})")
            lines.append("=" * 50)
            for listing in new_listings:
                name = listing.get("name") or listing.get("address") or "Unknown"
                price = listing.get("price") or 0
                distance = listing.get("distance")
                dist_str = f"{distance:.1f} mi" if distance else "N/A"
                lines.append(f"• {name}")
                lines.append(f"  Price: ${price:,.0f} | Distance: {dist_str}")
                lines.append(f"  {listing.get('zillow_url', '')}")
                lines.append("")
        else:
            lines.append("No new listings matching your criteria today.")

        lines.append("")
        lines.append("📊 ASSUMPTIONS")
        lines.append("=" * 50)
        lines.append(get_assumptions_text())

        return "\n".join(lines)

    def _send_email(
        self,
        recipient: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        """Send the email via Gmail SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.gmail_address
        msg["To"] = recipient

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.gmail_app_password)
                server.sendmail(self.gmail_address, recipient, msg.as_string())
            print(f"Email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
