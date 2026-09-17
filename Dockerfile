FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy application files
COPY generate_html_profile.py .
# Redesigned hosted-HTML profile generator
COPY inject_v2.py .
COPY dimension_content.py .
COPY narrative_v2.py .
COPY ai_narrative.py .
COPY lead_engine.py .
# Working Style (V3) layer modules
COPY working_style.py .
COPY working_style_content.py .
COPY working_style_content_lead.py .
COPY working_style_html.py .
COPY generate_manager_report.py .
# Dynamic Leadership Insight Report (team layer)
COPY generate_leader_report.py .
COPY team_lead_engine.py .
# Leadership Insight Report v2 (wired Claude Design template + pipeline)
COPY tpl_logo_email.png .
COPY lir_core.py .
COPY lir_compose.py .
COPY lir_render.py .
COPY lir_composition_spec.md .
COPY lir_template_wired.html .
COPY api_server.py .
# Between-sessions curriculum capture page route
COPY capture_route.py .
# Soft Skills + AI Communication assessment report (PDF)
COPY assessment_report.py .
COPY assessment_route.py .
COPY assessment_fonts.json .

# Copy HTML profile templates
COPY templates/ ./templates/
# Redesigned self-contained HTML templates (hosted profiles)
COPY templates_v2/ ./templates_v2/

# Static take-home assets (Resource Pack, Leadership Field Guide)
COPY assets/ ./assets/


EXPOSE 8000

CMD ["python3", "api_server.py"]
