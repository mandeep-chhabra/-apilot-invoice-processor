"""
APilot - AI-Powered Invoice Processing Application

Streamlit UI for invoice processing and decision making.
"""
import streamlit as st
import uuid
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
import hmac

from apilot import config
from apilot.database import db
from apilot.models import InvoiceRun, ExtractedInvoiceData, ProcessingResult
from apilot.services import (
    PDFExtractor, validate_pdf, get_extractor, match_vendor, match_po,
    check_duplicate, validate_invoice, make_decision, create_audit_event
)


# Page configuration
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide"
)


def init_session_state():
    """Initialize Streamlit session state."""
    if 'current_run' not in st.session_state:
        st.session_state.current_run = None
    if 'processing_result' not in st.session_state:
        st.session_state.processing_result = None
    if 'gemini_calls' not in st.session_state:
        st.session_state.gemini_calls = 0


def show_dashboard():
    """Display dashboard with metrics and recent activity."""
    st.title(f"{config.APP_ICON} APilot - AI Invoice Processing")
    st.markdown("### Accounts Payable Decision Engine")

    # Get statistics
    stats = db.get_stats()

    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Processed", stats['total'])
    with col2:
        st.metric("Approved", stats['approved'], delta_color="green")
    with col3:
        st.metric("In Review", stats['review'], delta_color="orange")
    with col4:
        st.metric("Rejected", stats['rejected'], delta_color="red")
    with col5:
        st.metric("Failed", stats['failed'], delta_color="red")

    st.divider()

    # Recent activity
    st.subheader("Recent Processing Activity")
    runs = db.get_all_runs(limit=20)

    if runs:
        import pandas as pd

        # Create a dropdown to select which invoice to view
        st.subheader("Recent Processing Activity")

        # Create a selection dropdown
        run_options = {f"{run.timestamp.strftime('%Y-%m-%d %H:%M')} - {run.original_filename} ({run.business_decision or 'Processing'})": run for run in runs}
        selected_label = st.selectbox("Select an invoice to view details:", list(run_options.keys()))
        selected_run = run_options[selected_label]

        st.divider()

        # Show details of selected run
        if selected_run:
            # Display extracted data
            st.markdown("### Extracted Data")
            if selected_run.extracted_data:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Vendor:** {selected_run.extracted_data.vendor_name or 'N/A'}")
                    st.write(f"**Invoice #:** {selected_run.extracted_data.invoice_number or 'N/A'}")
                    st.write(f"**Date:** {selected_run.extracted_data.invoice_date or 'N/A'}")
                    st.write(f"**PO Ref:** {selected_run.extracted_data.po_reference or 'N/A'}")
                with col2:
                    st.write(f"**Total:** {selected_run.extracted_data.invoice_total or 'N/A'}")
                    st.write(f"**Currency:** {selected_run.extracted_data.currency or 'N/A'}")
                    st.write(f"**Subtotal:** {selected_run.extracted_data.subtotal or 'N/A'}")

            st.divider()

            # Display validation results
            if selected_run.validation_results:
                st.markdown("### Validation Results")
                for result in selected_run.validation_results:
                    status_icon = {"PASS": "✅", "REVIEW_REQUIRED": "⚠️", "FAIL": "❌", "NOT_APPLICABLE": "➖"}.get(result.status, "➖")
                    with st.container(border=True):
                        st.write(f"{status_icon} **{result.rule_name}**: {result.explanation}")
                        if result.expected and result.actual:
                            st.caption(f"Expected: {result.expected} | Actual: {result.actual}")

            st.divider()

            # Display final decision
            st.markdown("### Final Decision")
            decision_color = {"APPROVE": "green", "REVIEW": "orange", "REJECT": "red", None: "gray"}
            decision_icon = {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "❌", None: "⏳"}
            st.markdown(f"{decision_icon.get(selected_run.business_decision, '⏳')} **{selected_run.business_decision or 'Processing'}**")
            if selected_run.decision_explanation:
                st.write(selected_run.decision_explanation)
    else:
        st.info("No invoices processed yet. Upload an invoice to get started.")

    # Quick actions
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Process New Invoice", type="primary", use_container_width=True):
            st.session_state['nav'] = 'process'
            st.rerun()
    with col2:
        if st.button("📊 View Reference Data", use_container_width=True):
            st.session_state['nav'] = 'reference'
            st.rerun()


def process_invoice():
    """Process a new invoice through the complete workflow."""
    st.title(f"{config.APP_ICON} Process Invoice")

    # Add back button at the top
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state['nav'] = 'dashboard'
            st.rerun()

    st.divider()

    # File upload
    uploaded_file = st.file_uploader(
        "Upload Invoice PDF",
        type=['pdf'],
        help="Upload a vendor invoice PDF for processing"
    )

    if uploaded_file:
        # Save uploaded file temporarily
        temp_dir = Path(config.UPLOAD_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_path = temp_dir / uploaded_file.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Validate PDF
        is_valid, error_msg = validate_pdf(str(temp_path))

        if not is_valid:
            st.error(f"Invalid PDF: {error_msg}")
            return

        # Initialize extractor
        extractor = PDFExtractor()

        # Process stages
        stages = []
        stages_completed = []

        # Stage 1: Extract text
        with st.status("Stage 1: Extracting text from PDF...", expanded=True) as status:
            try:
                text, method = extractor.extract(str(temp_path))

                # Calculate file hash for caching
                with open(temp_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                stages_completed.append("extraction")

                if method == "native":
                    st.success(f"Extracted {len(text)} characters using native PDF text")
                elif method == "ocr":
                    st.success(f"Extracted {len(text)} characters using OCR")
                else:
                    st.warning("No text could be extracted from the PDF")

                stages.append({
                    "stage": "Text Extraction",
                    "status": "completed",
                    "details": f"Method: {method}, Characters: {len(text)}"
                })
            except Exception as e:
                st.error(f"Extraction failed: {str(e)}")
                return

        # Stage 2: Check cache
        with st.status("Stage 2: Checking extraction cache...", expanded=True) as status:
            cached_data = db.get_cached_extraction(file_hash)

            if cached_data:
                extracted_data = cached_data
                st.success("Using cached extraction result")
                stages_completed.append("cache")
                stages.append({
                    "stage": "Cache Check",
                    "status": "completed",
                    "details": "Found cached extraction"
                })
            else:
                # Stage 3: Gemini extraction
                with st.status("Stage 3: Gemini extraction...", expanded=True) as status:
                    gemini = get_extractor()

                    if not gemini.is_available():
                        st.error("Gemini API not available. Please configure API key in .env")
                        return

                    try:
                        extracted_data = gemini.extract(text)
                        st.session_state.gemini_calls += 1

                        # Cache successful extraction
                        if extracted_data and not extracted_data.extraction_warnings:
                            db.cache_extraction(file_hash, extracted_data)
                            st.success("Extraction complete and cached")
                        else:
                            st.warning("Extraction completed with warnings")

                        stages_completed.append("gemini")
                        stages.append({
                            "stage": "Gemini Extraction",
                            "status": "completed",
                            "details": f"Extracted {len(extracted_data.line_items)} line items"
                        })
                    except Exception as e:
                        st.error(f"Gemini extraction failed: {str(e)}")
                        return

        # Stage 4: Vendor matching
        with st.status("Stage 4: Matching vendor...", expanded=True) as status:
            vendor_match = match_vendor(extracted_data)

            if vendor_match.vendor:
                st.success(f"Vendor matched: {vendor_match.vendor.name} ({vendor_match.match_type})")
            else:
                st.warning("Vendor not found in reference data")

            stages_completed.append("vendor_match")
            stages.append({
                "stage": "Vendor Matching",
                "status": "completed",
                "details": vendor_match.explanation
            })

        # Stage 5: PO matching
        with st.status("Stage 5: Matching purchase order...", expanded=True) as status:
            po_match = match_po(extracted_data, vendor_match)

            if po_match.po:
                balance = db.get_po_balance(po_match.po.id)
                st.success(f"PO matched: {po_match.po.po_number} (Balance: {balance.remaining_balance})")
            elif po_match.candidate_pos:
                st.warning(f"Found {len(po_match.candidate_pos)} candidate POs")
            else:
                st.warning("No PO matched")

            stages_completed.append("po_match")
            stages.append({
                "stage": "PO Matching",
                "status": "completed",
                "details": po_match.explanation
            })

        # Get PO balance
        po_balance = None
        if po_match.po:
            po_balance = db.get_po_balance(po_match.po.id)

        # Stage 6: Duplicate detection
        with st.status("Stage 6: Checking for duplicates...", expanded=True) as status:
            dup_check = check_duplicate(file_hash, extracted_data, vendor_match)

            if dup_check.is_duplicate:
                st.error(f"Duplicate detected: {dup_check.duplicate_type}")
            else:
                st.success("No duplicates found")

            stages_completed.append("duplicate")
            stages.append({
                "stage": "Duplicate Detection",
                "status": "completed",
                "details": dup_check.explanation
            })

        # Stage 7: Validation
        with st.status("Stage 7: Running validations...", expanded=True) as status:
            validation_results = validate_invoice(
                extracted_data, vendor_match, po_match, dup_check, po_balance
            )

            passed = sum(1 for r in validation_results if r.status == "PASS")
            failed = sum(1 for r in validation_results if r.status == "FAIL")
            review = sum(1 for r in validation_results if r.status == "REVIEW_REQUIRED")

            st.info(f"Validation: {passed} passed, {failed} failed, {review} review required")

            stages_completed.append("validation")
            stages.append({
                "stage": "Validation",
                "status": "completed",
                "details": f"{passed} passed, {failed} failed, {review} review"
            })

        # Stage 8: Decision
        with st.status("Stage 8: Making decision...", expanded=True) as status:
            decision, explanation = make_decision(
                validation_results, vendor_match, po_match, dup_check, po_balance, extracted_data
            )

            decision_color = {"APPROVE": "green", "REVIEW": "orange", "REJECT": "red"}.get(decision, "gray")
            st.success(f"Decision: **{decision}**")

            stages_completed.append("decision")
            stages.append({
                "stage": "Decision",
                "status": "completed",
                "details": f"{decision}: {explanation}"
            })

        # Stage 9: Save result
        with st.status("Stage 9: Saving results...", expanded=True) as status:
            run_id = str(uuid.uuid4())

            run = InvoiceRun(
                run_id=run_id,
                original_filename=uploaded_file.name,
                file_hash=file_hash,
                extracted_data=extracted_data,
                extraction_status="success",
                vendor_match=vendor_match,
                po_match=po_match,
                duplicate_check=dup_check,
                po_balance=po_balance,
                validation_results=validation_results,
                business_decision=decision,
                decision_explanation=explanation,
                processing_status="completed",
                timestamp=datetime.now()
            )

            # Save run
            db.save_run(run)

            # Create allocation if approved
            if decision == "APPROVE" and po_match.po and extracted_data.invoice_total:
                db.add_allocation(
                    po_match.po.id,
                    run_id,
                    extracted_data.invoice_total,
                    decision
                )

            st.success(f"Run saved with ID: {run_id[:8]}...")
            stages_completed.append("save")

        # Display results
        st.divider()
        st.subheader("Processing Results")

        # Decision display
        decision_emoji = {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "❌"}.get(decision, "❓")
        st.markdown(f"## {decision_emoji} Decision: {decision}")
        st.markdown(f"**Explanation:** {explanation}")

        # Extracted data
        with st.expander("Extracted Invoice Data", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Vendor Information**")
                st.write(f"Name: {extracted_data.vendor_name or 'N/A'}")
                st.write(f"Tax ID: {extracted_data.vendor_tax_id or 'N/A'}")

                st.markdown("**Invoice Details**")
                st.write(f"Invoice #: {extracted_data.invoice_number or 'N/A'}")
                st.write(f"Date: {extracted_data.invoice_date or 'N/A'}")
                st.write(f"Due Date: {extracted_data.due_date or 'N/A'}")
                st.write(f"PO Reference: {extracted_data.po_reference or 'N/A'}")

            with col2:
                st.markdown("**Financial Information**")
                st.write(f"Currency: {extracted_data.currency or 'N/A'}")
                st.write(f"Subtotal: {extracted_data.subtotal or 'N/A'}")
                st.write(f"Tax: {', '.join([str(t.get('amount', 'N/A')) for t in extracted_data.tax_components]) if extracted_data.tax_components else 'N/A'}")
                st.write(f"Shipping: {extracted_data.shipping or 'N/A'}")
                st.write(f"Discount: {extracted_data.discount or 'N/A'}")
                st.write(f"**Total: {extracted_data.invoice_total or 'N/A'}**")

            if extracted_data.missing_fields:
                st.warning(f"Missing fields: {', '.join(extracted_data.missing_fields)}")

            if extracted_data.extraction_warnings:
                st.warning(f"Warnings: {', '.join(extracted_data.extraction_warnings)}")

        # PO Balance
        if po_balance:
            with st.expander("PO Balance Information", expanded=True):
                st.write(f"PO Number: {po_balance.po_number}")
                st.write(f"Approved Amount: {po_balance.approved_amount} {po_balance.currency}")
                st.write(f"Previously Recorded: {po_balance.recorded_amount} {po_balance.currency}")
                st.write(f"**Remaining Balance: {po_balance.remaining_balance} {po_balance.currency}**")

        # Validation results
        with st.expander("Validation Results", expanded=True):
            for result in validation_results:
                status_icon = {
                    "PASS": "✅",
                    "FAIL": "❌",
                    "REVIEW_REQUIRED": "⚠️"
                }.get(result.status, "❓")

                st.write(f"{status_icon} **{result.rule_name}**: {result.status}")
                st.write(f"   {result.explanation}")
                st.markdown("---")

        # Gemini calls counter
        st.info(f"Gemini API calls this session: {st.session_state.gemini_calls}")

        # Clean up temp file
        try:
            temp_path.unlink()
        except:
            pass


def view_run_details(run_id: str = None):
    """View details of a specific invoice run."""
    if not run_id:
        run_id = st.query_params.get("run_id")

    if not run_id:
        st.error("No run ID provided")
        return

    run = db.get_run(run_id)

    if not run:
        st.error("Run not found")
        return

    st.title(f"Run Details: {run.run_id[:8]}...")

    # Back button
    if st.button("← Back to Dashboard"):
        st.session_state['nav'] = 'dashboard'
        st.rerun()

    # Decision display
    decision_emoji = {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "❌"}.get(run.business_decision, "❓")
    st.markdown(f"## {decision_emoji} Decision: {run.business_decision or 'Processing'}")
    st.markdown(f"**Explanation:** {run.decision_explanation}")

    # Basic info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Filename", run.original_filename)
    with col2:
        st.metric("Status", run.processing_status)
    with col3:
        st.metric("Date", run.timestamp.strftime("%Y-%m-%d %H:%M"))

    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["Invoice Data", "Vendor & PO", "Validation", "Audit"])

    with tab1:
        if run.extracted_data:
            data = run.extracted_data

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Vendor")
                st.write(f"**Name:** {data.vendor_name or 'N/A'}")
                st.write(f"**Tax ID:** {data.vendor_tax_id or 'N/A'}")

                st.markdown("### Invoice")
                st.write(f"**Invoice #:** {data.invoice_number or 'N/A'}")
                st.write(f"**Date:** {data.invoice_date or 'N/A'}")
                st.write(f"**Due Date:** {data.due_date or 'N/A'}")
                st.write(f"**PO Reference:** {data.po_reference or 'N/A'}")

            with col2:
                st.markdown("### Financial")
                st.write(f"**Currency:** {data.currency or 'N/A'}")
                st.write(f"**Subtotal:** {data.subtotal or 'N/A'}")
                st.write(f"**Total:** {data.invoice_total or 'N/A'}")

                if data.missing_fields:
                    st.warning(f"**Missing Fields:** {', '.join(data.missing_fields)}")
                if data.extraction_warnings:
                    st.warning(f"**Warnings:** {', '.join(data.extraction_warnings)}")

    with tab2:
        if run.vendor_match:
            st.markdown("### Vendor Match")
            if run.vendor_match.vendor:
                st.write(f"**Matched Vendor:** {run.vendor_match.vendor.name}")
                st.write(f"**Status:** {run.vendor_match.vendor.status}")
            st.write(f"**Match Type:** {run.vendor_match.match_type or 'N/A'}")
            st.write(f"**Confidence:** {run.vendor_match.confidence}")
            st.write(f"**Explanation:** {run.vendor_match.explanation}")

        st.markdown("---")

        if run.po_match:
            st.markdown("### PO Match")
            if run.po_match.po:
                st.write(f"**Matched PO:** {run.po_match.po.po_number}")
                st.write(f"**Status:** {run.po_match.po.status}")
            if run.po_match.candidate_pos:
                st.write(f"**Candidate POs:** {', '.join([p.po_number for p in run.po_match.candidate_pos])}")
            st.write(f"**Match Type:** {run.po_match.match_type or 'N/A'}")
            st.write(f"**Confidence:** {run.po_match.confidence}")
            st.write(f"**Explanation:** {run.po_match.explanation}")

        if run.po_balance:
            st.markdown("---")
            st.markdown("### PO Balance")
            st.write(f"**Approved:** {run.po_balance.approved_amount} {run.po_balance.currency}")
            st.write(f"**Recorded:** {run.po_balance.recorded_amount} {run.po_balance.currency}")
            st.write(f"**Remaining:** {run.po_balance.remaining_balance} {run.po_balance.currency}")

    with tab3:
        if run.validation_results:
            for result in run.validation_results:
                status_icon = {"PASS": "✅", "FAIL": "❌", "REVIEW_REQUIRED": "⚠️"}.get(result.status, "❓")
                st.markdown(f"**{status_icon} {result.rule_name}:** {result.status}")
                st.write(f"_{result.explanation}_")
                st.markdown("---")

    with tab4:
        if run.audit_events:
            for event in run.audit_events:
                st.write(f"**{event.timestamp.strftime('%H:%M:%S')}** - {event.stage}: {event.explanation}")
        else:
            st.info("No audit events recorded")


def view_reference_data():
    """Display reference data (vendors, POs)."""
    st.title("📚 Reference Data")

    tab1, tab2 = st.tabs(["👥 Vendors", "📦 Purchase Orders"])

    with tab1:
        st.subheader("Vendors")
        vendors = db.get_all_vendors()

        if vendors and len(vendors) > 0:
            st.success(f"✅ Found {len(vendors)} vendors")

            for v in vendors:
                status_color = "✅" if v.status == "active" else "🚫"
                with st.container(border=True):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        st.write(f"**ID:** {v.id}")
                    with col2:
                        st.write(f"**{v.name}**")
                    with col3:
                        st.write(f"{status_color} {v.status.upper()}")
                    st.caption(f"Tax ID: {v.tax_id or 'N/A'}")
        else:
            st.warning("⚠️ No vendors found in database")

    with tab2:
        st.subheader("Purchase Orders")
        pos = db.get_all_pos()

        if pos and len(pos) > 0:
            st.success(f"✅ Found {len(pos)} purchase orders")

            for p in pos:
                balance = db.get_po_balance(p.id)
                remaining = balance.remaining_balance if balance else p.approved_amount

                with st.container(border=True):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**{p.po_number}**")
                        st.caption(f"Vendor: {p.vendor.name if p.vendor else 'N/A'}")
                    with col2:
                        st.write(f"{p.currency} {p.approved_amount}")

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Tolerance", f"{p.tolerance_percent}%")
                    with col_b:
                        st.metric("Remaining", f"{remaining}")
                    with col_c:
                        status_emoji = "✅" if p.status == "active" else "⚠️"
                        st.write(f"{status_emoji} {p.status.upper()}")
        else:
            st.warning("⚠️ No purchase orders found in database")

    st.divider()
    if st.button("← Back to Dashboard"):
        st.session_state['nav'] = 'dashboard'
        st.rerun()

with st.expander("Admin: Reset invoice data"):
    # Password stored in Streamlit secrets
    admin_password = st.text_input(
        "Admin password",
        type="password",
        key="reset_admin_password"
    )

    password_correct = hmac.compare_digest(
        admin_password,
        st.secrets["ADMIN_PASSWORD"]
    ) if admin_password else False

    if admin_password and not password_correct:
        st.warning("Incorrect admin password.")

    confirm = st.checkbox(
        "I understand this will delete all processed invoices "
        "and cached extraction results",
        disabled=not password_correct
    )

    if st.button(
        "Clear All Invoice Data",
        type="secondary",
        disabled=not password_correct or not confirm
    ):
        db_path = Path("data/apilot.db")

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM extraction_cache")
                conn.execute("DELETE FROM invoice_runs")

            st.success(
                "Processed invoices and extraction cache "
                "cleared successfully."
            )
            st.rerun()

        except sqlite3.Error as e:
            st.error(f"Could not clear invoice data: {e}")



def main():
    """Main application entry point."""
    init_session_state()

    # Navigation
    if 'nav' not in st.session_state:
        st.session_state['nav'] = 'dashboard'

    nav = st.session_state['nav']

    if nav == 'dashboard':
        show_dashboard()
    elif nav == 'process':
        process_invoice()
    elif nav == 'reference':
        view_reference_data()
    elif nav == 'details':
        view_run_details()


if __name__ == "__main__":
    main()
