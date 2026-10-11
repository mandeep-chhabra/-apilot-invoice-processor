"""Clear all processed invoices from the database."""
import sqlite3
from pathlib import Path

def main():
    """Delete all processed invoice runs."""
    db_path = Path("data/apilot.db")

    print("=" * 50)
    print("CLEARING PROCESSED INVOICES")
    print("=" * 50)

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    # Connect directly to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Get count of runs before deletion
        cursor.execute("SELECT COUNT(*) FROM invoice_runs")
        count_before = cursor.fetchone()[0]
        print(f"\nFound {count_before} invoice runs to delete...")

        # Delete audit events first (foreign key constraint)
        cursor.execute("DELETE FROM audit_events")
        events_deleted = cursor.rowcount
        print(f"  Deleted {events_deleted} audit events")

        # Delete invoice runs
        cursor.execute("DELETE FROM invoice_runs")
        runs_deleted = cursor.rowcount
        print(f"  Deleted {runs_deleted} invoice runs")

        # Commit changes
        conn.commit()

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM invoice_runs")
        count_after = cursor.fetchone()[0]

        print(f"\nOK Deleted {runs_deleted} invoice runs")
        print(f"OK Remaining runs: {count_after}")

        # Show updated statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN business_decision = 'APPROVE' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN business_decision = 'REVIEW' THEN 1 ELSE 0 END) as review,
                SUM(CASE WHEN business_decision = 'REJECT' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN business_decision IS NULL THEN 1 ELSE 0 END) as failed
            FROM invoice_runs
        """)
        result = cursor.fetchone()

        print(f"\nUpdated Statistics:")
        print(f"  Total Processed: {result[0] or 0}")
        print(f"  Approved: {result[1] or 0}")
        print(f"  In Review: {result[2] or 0}")
        print(f"  Rejected: {result[3] or 0}")
        print(f"  Failed: {result[4] or 0}")

        print("\nOK Database cleared! Ready for testing.")
        print("=" * 50)

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
