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

# GitHub repo for favorite/feedback links
GITHUB_REPO = "toxicapplejuice/austin-house-hunter"

# Professional color palette (inspired by modern SaaS)
COLORS = {
    "primary": "#0F172A",      # Slate 900 - headers
    "secondary": "#334155",    # Slate 700 - subtext
    "accent": "#3B82F6",       # Blue 500 - links, CTAs
    "accent_hover": "#2563EB", # Blue 600
    "success": "#10B981",      # Emerald 500 - favorites
    "warning": "#F59E0B",      # Amber 500
    "background": "#F8FAFC",   # Slate 50
    "card": "#FFFFFF",
    "border": "#E2E8F0",       # Slate 200
    "text": "#1E293B",         # Slate 800
    "muted": "#64748B",        # Slate 500
}


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
        preferences: dict[str, Any] | None = None,
    ) -> bool:
        """Send an email with house listings in table format."""
        favorites = favorites or []
        preferences = preferences or {}
        date_str = datetime.now().strftime("%B %d, %Y")

        if not new_listings and not favorites:
            subject = f"Austin House Update - No New Matches"
        else:
            subject = f"Austin House Update - {len(new_listings)} New Properties"

        html_content = self._build_html(new_listings, favorites, date_str, preferences)
        text_content = self._build_text(new_listings, favorites, preferences)

        return self._send_email(recipient, subject, html_content, text_content)

    def _get_bob_reasoning(self, preferences: dict[str, Any], favorites_count: int) -> str:
        """Generate Bob's chain of thought explaining why he picked these properties."""
        reasons = []

        preferred_neighborhoods = preferences.get("preferred_neighborhoods", [])
        ideal_price = preferences.get("ideal_price")
        ideal_sqft = preferences.get("ideal_sqft")
        ideal_beds = preferences.get("ideal_beds")
        hoa_pref = preferences.get("hoa_preference")

        # Check how much we've learned
        has_learned = bool(preferred_neighborhoods or ideal_price or ideal_sqft or hoa_pref is not None)

        if not has_learned and favorites_count == 0:
            # No data yet - explain we're just starting
            return (
                "I'm still learning your preferences! Currently showing listings sorted by price (highest first). "
                "Save some favorites and I'll start identifying patterns in what you like. Bello!"
            )

        if not has_learned and favorites_count > 0:
            # Have favorites but haven't processed them yet
            return (
                "I see you have some favorites saved. I'm analyzing them to understand your preferences. "
                "For now, listings are sorted by price—I'll get smarter with each update."
            )

        # We have learned preferences - explain our reasoning
        if preferred_neighborhoods:
            top_neighborhoods = preferred_neighborhoods[:3]
            if len(top_neighborhoods) == 1:
                reasons.append(f"you've shown interest in <strong>{top_neighborhoods[0]}</strong>")
            else:
                neighborhoods_str = ", ".join(top_neighborhoods[:-1]) + f" and {top_neighborhoods[-1]}"
                reasons.append(f"you're drawn to <strong>{neighborhoods_str}</strong>")

        if ideal_price:
            reasons.append(f"your target range centers around <strong>${ideal_price:,.0f}</strong>")

        if ideal_beds:
            beds_rounded = round(ideal_beds)
            reasons.append(f"you prefer <strong>{beds_rounded}-bedroom</strong> homes")

        if ideal_sqft:
            reasons.append(f"you gravitate toward <strong>{ideal_sqft:,.0f} sqft</strong>")

        if hoa_pref is not None:
            if hoa_pref:
                reasons.append("you're comfortable with HOA communities")
            else:
                reasons.append("you prefer properties <strong>without HOA</strong>")

        if reasons:
            # Build the explanation
            reasoning = "Based on your favorites, I've noticed " + reasons[0]
            if len(reasons) > 1:
                reasoning += ", " + ", ".join(reasons[1:-1])
                if len(reasons) > 2:
                    reasoning += ","
                reasoning += " and " + reasons[-1]
            reasoning += ". I'm prioritizing listings that match these patterns."
            return reasoning

        return (
            "I'm building a profile of your preferences. Keep saving favorites "
            "and I'll refine my recommendations over time."
        )

    def _get_bob_greeting(self, new_count: int, favorites_count: int) -> str:
        """Get Bob's personalized greeting (with 15% minion flavor)."""
        greetings = [
            "Bello! Bob here with your Austin property update.",
            "Hey there! Bob checking in with your latest property report.",
            "Hello! Here's what I found in the Austin market.",
        ]
        greeting = greetings[datetime.now().day % len(greetings)]

        if new_count > 0 and favorites_count > 0:
            message = f"""
            {greeting}

            I've been monitoring the market and found <strong>{new_count} new properties</strong>
            that match your criteria. I've also kept your <strong>{favorites_count} saved favorites</strong>
            updated with the latest info.

            Take a look below—click the star on any listing to save it. Bee-do!
            """
        elif new_count > 0:
            message = f"""
            {greeting}

            Good news! I found <strong>{new_count} new properties</strong> that match what you're looking for.

            Browse through the listings below. If something catches your eye, click the star to add it to
            your favorites and I'll keep tracking it for you.
            """
        elif favorites_count > 0:
            message = f"""
            {greeting}

            No new listings matched your criteria today, but I'm keeping an eye on your
            <strong>{favorites_count} saved favorites</strong>. The Austin market moves quickly—I'll
            let you know as soon as something pops up!
            """
        else:
            message = f"""
            {greeting}

            It's a quiet day on the Austin market—no new listings matched your criteria.
            Don't worry, I'm continuously scanning. I'll reach out as soon as I find
            something promising. Banana! (Sorry, got excited.)
            """

        return message.strip()

    def _build_listing_row(self, listing: dict[str, Any], show_favorite_link: bool = True) -> str:
        """Build a single table row for a listing."""
        name = listing.get("name") or listing.get("address") or "Unknown"
        if len(name) > 35:
            name = name[:32] + "..."

        # Price (2nd column)
        price = listing.get("price") or 0
        price_str = f"${price:,.0f}" if price else "N/A"

        # Bed/Bath
        beds = listing.get("beds") or "?"
        baths = listing.get("baths") or "?"
        beds_baths = f"{beds}bd/{baths}ba"

        # Neighborhood with direction
        neighborhood = listing.get("neighborhood") or "Austin"
        direction = listing.get("direction") or ""
        if direction and direction != "Central":
            neighborhood_display = f"{neighborhood} ({direction})"
        else:
            neighborhood_display = neighborhood
        if len(neighborhood_display) > 28:
            neighborhood_display = neighborhood_display[:25] + "..."

        # HOA
        has_hoa = listing.get("has_hoa")
        hoa_display = "Yes" if has_hoa else "No"

        # Distance to Sapphire with Google Maps directions link
        distance = listing.get("distance")
        lat = listing.get("latitude")
        lon = listing.get("longitude")
        # Sapphire coordinates (downtown Austin)
        sapphire_lat, sapphire_lon = 30.2672, -97.7431
        if distance and lat and lon:
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={sapphire_lat},{sapphire_lon}"
            distance_str = f'<a href="{maps_url}" style="color: {COLORS["accent"]}; text-decoration: none;">{distance:.1f} mi</a>'
        elif distance:
            distance_str = f"{distance:.1f} mi"
        else:
            distance_str = "N/A"

        # Financials - combined into one column
        down = calculate_down_payment(price) if price else 0
        monthly = calculate_total_monthly(price) if price else 0
        if down and monthly:
            financials_str = f"${down:,.0f} | ${monthly:,.0f}/mo"
        else:
            financials_str = "N/A"

        zillow_url = listing.get("zillow_url") or "#"
        zpid = listing.get("zpid") or ""

        # Favorite link (no labels param - workflow detects by title prefix)
        favorite_url = f"https://github.com/{GITHUB_REPO}/issues/new?title=FAVORITE:%20{zpid}&body=Favoriting%20property%20{zpid}"

        favorite_cell = ""
        if show_favorite_link:
            favorite_cell = f'''
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; text-align: center;">
                <a href="{favorite_url}" style="display: inline-block; background-color: {COLORS['success']};
                   color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px;
                   font-size: 12px; font-weight: 500;">★ Save</a>
            </td>'''

        # Column order: Property, Price, Bed/Bath, Neighborhood, HOA, To Sapphire, Down | Monthly, Action
        return f'''
        <tr>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']};">
                <a href="{zillow_url}" style="color: {COLORS['accent']}; text-decoration: none; font-weight: 500;">{name}</a>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; font-weight: 600; color: {COLORS['text']};">{price_str}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['secondary']};">{beds_baths}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['secondary']}; font-size: 13px;">{neighborhood_display}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['secondary']};">{hoa_display}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['secondary']};">{distance_str}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['secondary']}; font-size: 12px;">{financials_str}</td>
            {favorite_cell}
        </tr>
        '''

    def _build_html(
        self,
        new_listings: list[dict[str, Any]],
        favorites: list[dict[str, Any]],
        date_str: str,
        preferences: dict[str, Any] | None = None,
    ) -> str:
        """Build HTML email content with tables."""
        preferences = preferences or {}

        bob_greeting = self._get_bob_greeting(len(new_listings), len(favorites))
        bob_reasoning = self._get_bob_reasoning(preferences, len(favorites))

        # Table headers - Column order: Property, Price, Bed/Bath, Neighborhood, HOA, To Sapphire, Down | Monthly, Action
        headers_with_action = f'''
            <tr style="background-color: #F1F5F9;">
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Property</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Price</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Bed/Bath</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Neighborhood</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">HOA</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">To Sapphire</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Down | Monthly</th>
                <th style="padding: 12px 8px; text-align: center; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Action</th>
            </tr>
        '''

        headers_no_action = f'''
            <tr style="background-color: #F1F5F9;">
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Property</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Price</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Bed/Bath</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Neighborhood</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">HOA</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">To Sapphire</th>
                <th style="padding: 12px 8px; text-align: left; border-bottom: 2px solid {COLORS['border']}; color: {COLORS['primary']}; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Down | Monthly</th>
            </tr>
        '''

        # Favorites section
        favorites_html = ""
        if favorites:
            favorites_rows = "".join(
                self._build_listing_row(l, show_favorite_link=False) for l in favorites
            )
            favorites_html = f'''
            <div style="margin-bottom: 32px;">
                <div style="display: flex; align-items: center; margin-bottom: 16px;">
                    <div style="width: 4px; height: 24px; background-color: {COLORS['success']}; border-radius: 2px; margin-right: 12px;"></div>
                    <h2 style="color: {COLORS['primary']}; font-size: 18px; font-weight: 600; margin: 0;">
                        Your Saved Properties ({len(favorites)})
                    </h2>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <thead>
                            {headers_no_action}
                        </thead>
                        <tbody>
                            {favorites_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            '''

        # New listings section
        new_listings_html = ""
        if new_listings:
            new_rows = "".join(
                self._build_listing_row(l, show_favorite_link=True) for l in new_listings
            )
            new_listings_html = f'''
            <div style="margin-bottom: 32px;">
                <div style="display: flex; align-items: center; margin-bottom: 16px;">
                    <div style="width: 4px; height: 24px; background-color: {COLORS['accent']}; border-radius: 2px; margin-right: 12px;"></div>
                    <h2 style="color: {COLORS['primary']}; font-size: 18px; font-weight: 600; margin: 0;">
                        New Listings ({len(new_listings)})
                    </h2>
                </div>
                <div style="background-color: #FEF9C3; border-left: 4px solid #FCD34D; padding: 12px 16px; margin-bottom: 16px; border-radius: 0 8px 8px 0;">
                    <div style="color: {COLORS['text']}; font-size: 13px; line-height: 1.5;">
                        <strong style="color: #92400E;">Bob's Thinking:</strong> {bob_reasoning}
                    </div>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <thead>
                            {headers_with_action}
                        </thead>
                        <tbody>
                            {new_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            '''

        # Assumptions section
        assumptions = get_assumptions_text().replace("\n", "<br>")

        # Feedback link (no labels param - workflow detects by title prefix)
        feedback_url = f"https://github.com/{GITHUB_REPO}/issues/new?title=FEEDBACK:%20&body=Tell%20Bob%20what%20you%27d%20like%20to%20see%20more%20of%20(neighborhoods%2C%20price%20range%2C%20features)%3A%0A%0A"

        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                     padding: 0; margin: 0; background-color: {COLORS['background']};">
            <div style="max-width: 1000px; margin: 0 auto; padding: 32px 16px;">

                <!-- Header -->
                <div style="background: linear-gradient(135deg, {COLORS['primary']} 0%, #1E3A5F 100%);
                            padding: 32px; border-radius: 12px 12px 0 0; color: white;">
                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; opacity: 0.8; margin-bottom: 8px;">
                        Austin Property Report
                    </div>
                    <div style="font-size: 24px; font-weight: 600; margin-bottom: 4px;">
                        {date_str}
                    </div>
                </div>

                <!-- Bob's Message -->
                <div style="background-color: white; padding: 24px 32px; border-left: 1px solid {COLORS['border']};
                            border-right: 1px solid {COLORS['border']};">
                    <div style="display: flex; align-items: flex-start;">
                        <div style="width: 48px; height: 48px; background-color: #FCD34D; border-radius: 50%;
                                    display: flex; align-items: center; justify-content: center; margin-right: 16px; flex-shrink: 0;">
                            <span style="font-size: 20px;">🍌</span>
                        </div>
                        <div>
                            <div style="font-weight: 600; color: {COLORS['primary']}; margin-bottom: 4px;">Bob</div>
                            <div style="font-size: 12px; color: {COLORS['muted']}; margin-bottom: 12px;">Your Real Estate Minion</div>
                            <div style="color: {COLORS['text']}; line-height: 1.6; font-size: 14px;">
                                {bob_greeting}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Content -->
                <div style="background-color: {COLORS['background']}; padding: 32px;
                            border-left: 1px solid {COLORS['border']}; border-right: 1px solid {COLORS['border']};">
                    {favorites_html}
                    {new_listings_html}
                </div>

                <!-- Assumptions Footer -->
                <div style="background-color: white; padding: 24px 32px; border: 1px solid {COLORS['border']};
                            border-top: none;">
                    <div style="font-size: 12px; font-weight: 600; color: {COLORS['secondary']};
                                text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                        Calculation Assumptions
                    </div>
                    <div style="color: {COLORS['muted']}; font-size: 12px; line-height: 1.8;">
                        {assumptions}
                    </div>
                </div>

                <!-- Feedback Section -->
                <div style="background-color: {COLORS['primary']}; padding: 24px 32px; border-radius: 0 0 12px 12px;
                            text-align: center;">
                    <div style="color: white; font-size: 14px; margin-bottom: 12px;">
                        Want to adjust your search criteria? Let me know what you're looking for.
                    </div>
                    <a href="{feedback_url}" style="display: inline-block; background-color: #FCD34D;
                       color: #1F2937; padding: 10px 24px; text-decoration: none; border-radius: 6px;
                       font-size: 14px; font-weight: 600;">💬 Give Feedback</a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding: 24px; color: {COLORS['muted']}; font-size: 11px;">
                    Powered by Austin House Hunter
                </div>

            </div>
        </body>
        </html>
        '''

    def _build_text(
        self,
        new_listings: list[dict[str, Any]],
        favorites: list[dict[str, Any]],
        preferences: dict[str, Any] | None = None,
    ) -> str:
        """Build plain text email content."""
        preferences = preferences or {}
        lines = []
        lines.append("=" * 60)
        lines.append("AUSTIN PROPERTY REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Bello! Bob here, your real estate minion.")
        lines.append("")

        if favorites:
            lines.append(f"YOUR SAVED PROPERTIES ({len(favorites)})")
            lines.append("-" * 40)
            for listing in favorites:
                name = listing.get("name") or listing.get("address") or "Unknown"
                price = listing.get("price") or 0
                neighborhood = listing.get("neighborhood") or "Austin"
                lines.append(f"* {name}")
                lines.append(f"  ${price:,.0f} | {neighborhood}")
                lines.append(f"  {listing.get('zillow_url', '')}")
                lines.append("")

        if new_listings:
            # Add Bob's reasoning (strip HTML tags for plain text)
            import re
            reasoning = self._get_bob_reasoning(preferences, len(favorites))
            reasoning_plain = re.sub(r'<[^>]+>', '', reasoning)
            lines.append("BOB'S THINKING:")
            lines.append(reasoning_plain)
            lines.append("")
            lines.append(f"NEW LISTINGS ({len(new_listings)})")
            lines.append("-" * 40)
            for listing in new_listings:
                name = listing.get("name") or listing.get("address") or "Unknown"
                price = listing.get("price") or 0
                distance = listing.get("distance")
                dist_str = f"{distance:.1f} mi to Sapphire" if distance else "N/A"
                neighborhood = listing.get("neighborhood") or "Austin"
                lines.append(f"* {name}")
                lines.append(f"  ${price:,.0f} | {neighborhood} | {dist_str}")
                lines.append(f"  {listing.get('zillow_url', '')}")
                lines.append("")
        else:
            lines.append("No new listings matched your criteria today.")
            lines.append("")

        lines.append("")
        lines.append("CALCULATION ASSUMPTIONS")
        lines.append("-" * 40)
        lines.append(get_assumptions_text())
        lines.append("")
        lines.append("Want to see different properties? Give feedback:")
        lines.append(f"https://github.com/{GITHUB_REPO}/issues/new?title=FEEDBACK:%20")

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
