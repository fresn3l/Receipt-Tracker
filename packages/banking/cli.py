"""
Command-line interface for finance tracker.

This module provides a Click-based CLI with multiple subcommands for different
operations. The CLI integrates with all core components to provide a complete
command-line experience.

Available Commands:
    - import-csv: Import and process CSV files
    - summary: Show monthly spending summaries
    - categories: Display top spending categories
    - uncategorized: List uncategorized transactions
    - recategorize: Recategorize all stored transactions
    - export: Export transactions to JSON/CSV
    - stats: Show overall statistics

The CLI respects configuration settings and provides helpful error messages.

Example Usage:
    $ finance-tracker import-csv bank_statement.csv
    $ finance-tracker summary --year 2024 --month 1
    $ finance-tracker categories --limit 10
    $ finance-tracker export transactions.json --format json
"""

import logging
from pathlib import Path
from typing import Optional

import click

from banking.config import get_config
from banking.logging_config import setup_logging
from banking.workflow import FinanceTrackerWorkflow

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    help="Data directory for storing transactions",
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path], verbose: bool, data_dir: Optional[Path]):
    """Finance Tracker - Track and categorize your spending."""
    # Load configuration
    cfg = get_config(config)
    if data_dir:
        cfg.set("data.directory", str(data_dir))

    # Setup logging
    log_level = cfg.get("logging.level", "INFO")
    log_file = cfg.get("logging.file")
    if log_file:
        log_file = Path(log_file)
    setup_logging(level=log_level, log_file=log_file, verbose=verbose)

    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["data_dir"] = Path(cfg.get("data.directory", Path.home() / ".finance-tracker"))


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--account", help="Account identifier for transactions")
@click.option(
    "--no-categorize", is_flag=True, help="Skip automatic categorization"
)
@click.option(
    "--overwrite", is_flag=True, help="Overwrite existing categories"
)
@click.option(
    "--no-duplicate-check", is_flag=True, help="Skip duplicate detection"
)
@click.pass_context
def import_csv(
    ctx: click.Context,
    csv_file: Path,
    account: Optional[str],
    no_categorize: bool,
    overwrite: bool,
    no_duplicate_check: bool,
):
    """Import transactions from a CSV file."""
    cfg = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]

    auto_categorize = not no_categorize and cfg.get("categorization.auto_categorize", True)
    check_duplicates = not no_duplicate_check and cfg.get("duplicates.check_on_import", True)
    skip_duplicates = cfg.get("duplicates.skip_duplicates", True)

    click.echo(f"Importing transactions from {csv_file}...")

    workflow = FinanceTrackerWorkflow(data_dir=data_dir, account=account)
    transactions, stats = workflow.process_csv_file(
        csv_file,
        auto_categorize=auto_categorize,
        overwrite_categories=overwrite,
        check_duplicates=check_duplicates,
        skip_duplicates=skip_duplicates,
    )

    click.echo(f"\n✓ Imported {stats['new_transactions']} transactions")
    if stats.get("duplicates_found", 0) > 0:
        click.echo(f"  Found {stats['duplicates_found']} duplicates")
        if stats.get("duplicates_skipped", 0) > 0:
            click.echo(f"  Skipped {stats['duplicates_skipped']} duplicates")

    if auto_categorize and "categorized" in stats:
        click.echo(f"  Categorized: {stats['categorized']}/{stats.get('total_parsed', 0)}")
        click.echo(f"  Categorization rate: {stats.get('categorization_rate', 0):.1f}%")


@cli.command()
@click.option("--year", type=int, help="Filter by year")
@click.option("--month", type=int, help="Filter by month (requires --year)")
@click.pass_context
def summary(ctx: click.Context, year: Optional[int], month: Optional[int]):
    """Show spending summary."""
    data_dir = ctx.obj["data_dir"]

    if month and not year:
        click.echo("Error: --month requires --year", err=True)
        return

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    analyzer = workflow.analyze_spending(year=year, month=month)

    if month and year:
        # Show monthly summary
        summary_data = analyzer.get_monthly_summary(year, month)
        click.echo(f"\nMonthly Summary - {year}-{month:02d}")
        click.echo("=" * 50)
        click.echo(f"Total Income:    ${summary_data.total_income:,.2f}")
        click.echo(f"Total Expenses:  ${summary_data.total_expenses:,.2f}")
        click.echo(f"Net Amount:     ${summary_data.net_amount:,.2f}")
        if summary_data.savings_rate:
            click.echo(f"Savings Rate:   {summary_data.savings_rate:.1f}%")
        click.echo(f"Transactions:   {summary_data.transaction_count}")

        if summary_data.category_breakdown:
            click.echo("\nCategory Breakdown:")
            for category, amount in sorted(
                summary_data.category_breakdown.items(), key=lambda x: x[1], reverse=True
            ):
                click.echo(f"  {category:20s} ${amount:>10,.2f}")
    else:
        # Show all monthly summaries
        summaries = analyzer.get_all_monthly_summaries()
        if not summaries:
            click.echo("No transactions found.")
            return

        click.echo("\nMonthly Summaries")
        click.echo("=" * 80)
        click.echo(f"{'Month':<12} {'Income':>12} {'Expenses':>12} {'Net':>12} {'Savings':>10}")
        click.echo("-" * 80)

        for s in summaries:
            savings = f"{s.savings_rate:.1f}%" if s.savings_rate else "N/A"
            click.echo(
                f"{s.year}-{s.month:02d:<8} "
                f"${s.total_income:>10,.2f} "
                f"${s.total_expenses:>10,.2f} "
                f"${s.net_amount:>10,.2f} "
                f"{savings:>10}"
            )


@cli.command()
@click.option("--limit", default=10, help="Number of top categories to show")
@click.pass_context
def categories(ctx: click.Context, limit: int):
    """Show top spending categories."""
    data_dir = ctx.obj["data_dir"]

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    analyzer = workflow.analyze_spending()
    top_categories = analyzer.get_top_categories(limit=limit)

    if not top_categories:
        click.echo("No categorized transactions found.")
        return

    click.echo(f"\nTop {limit} Spending Categories")
    click.echo("=" * 80)
    click.echo(f"{'Category':<30} {'Total':>15} {'Avg':>15} {'Count':>10} {'%':>8}")
    click.echo("-" * 80)

    for pattern in top_categories:
        percentage = f"{pattern.percentage_of_total:.1f}%" if pattern.percentage_of_total else "N/A"
        click.echo(
            f"{pattern.category:<30} "
            f"${pattern.total_amount:>14,.2f} "
            f"${pattern.average_transaction:>14,.2f} "
            f"{pattern.transaction_count:>10} "
            f"{percentage:>8}"
        )


@cli.command()
@click.pass_context
def uncategorized(ctx: click.Context):
    """Show uncategorized transactions."""
    data_dir = ctx.obj["data_dir"]

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    uncategorized_txns = workflow.get_uncategorized_transactions()

    if not uncategorized_txns:
        click.echo("All transactions are categorized!")
        return

    click.echo(f"\nFound {len(uncategorized_txns)} uncategorized transactions:")
    click.echo("=" * 80)
    click.echo(f"{'Date':<12} {'Description':<40} {'Amount':>12}")
    click.echo("-" * 80)

    for txn in uncategorized_txns[:50]:  # Show first 50
        click.echo(f"{txn.date} {txn.description:<40} ${txn.absolute_amount:>10,.2f}")

    if len(uncategorized_txns) > 50:
        click.echo(f"\n... and {len(uncategorized_txns) - 50} more")


@cli.command()
@click.option("--overwrite", is_flag=True, help="Overwrite existing categories")
@click.pass_context
def recategorize(ctx: click.Context, overwrite: bool):
    """Recategorize all stored transactions."""
    data_dir = ctx.obj["data_dir"]

    click.echo("Recategorizing all transactions...")

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    stats = workflow.recategorize_all(overwrite=overwrite)

    click.echo(f"\n✓ Recategorized {stats['total']} transactions")
    click.echo(f"  Categorized: {stats['categorized']}")
    click.echo(f"  Uncategorized: {stats['uncategorized']}")
    click.echo(f"  Rate: {stats['categorization_rate']:.1f}%")


@cli.command()
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--format", "export_format", type=click.Choice(["json", "csv"]), default="json")
@click.pass_context
def export(ctx: click.Context, output_file: Path, export_format: str):
    """Export transactions to JSON or CSV file."""
    data_dir = ctx.obj["data_dir"]

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)

    if export_format == "json":
        workflow.storage.export_transactions_json(output_file)
    else:
        workflow.storage.export_transactions_csv(output_file)

    click.echo(f"✓ Exported transactions to {output_file}")


@cli.command()
@click.pass_context
def stats(ctx: click.Context):
    """Show general statistics."""
    data_dir = ctx.obj["data_dir"]

    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    analyzer = workflow.analyze_spending()

    total_income = analyzer.get_total_income()
    total_expenses = analyzer.get_total_expenses()
    net_amount = analyzer.get_net_amount()

    click.echo("\nOverall Statistics")
    click.echo("=" * 50)
    click.echo(f"Total Income:   ${total_income:,.2f}")
    click.echo(f"Total Expenses: ${total_expenses:,.2f}")
    click.echo(f"Net Amount:    ${net_amount:,.2f}")

    if total_income > 0:
        savings_rate = (net_amount / total_income) * 100
        click.echo(f"Savings Rate:  {savings_rate:.1f}%")


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()

