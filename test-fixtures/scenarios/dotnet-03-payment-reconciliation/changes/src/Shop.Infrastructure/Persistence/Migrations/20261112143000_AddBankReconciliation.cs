using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Shop.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddBankReconciliation : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "PaymentNote",
                schema: "billing",
                table: "Invoices");

            migrationBuilder.AddColumn<Guid>(
                name: "BankTransactionId",
                schema: "billing",
                table: "Payments",
                type: "uniqueidentifier",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "BankTransactions",
                schema: "billing",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    BankReference = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Amount = table.Column<decimal>(type: "decimal(18,2)", precision: 18, scale: 2, nullable: false),
                    Currency = table.Column<string>(type: "nchar(3)", fixedLength: true, maxLength: 3, nullable: false),
                    BookedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    RemittanceInformation = table.Column<string>(type: "nvarchar(500)", maxLength: 500, nullable: true),
                    CounterpartyIban = table.Column<string>(type: "nvarchar(34)", maxLength: 34, nullable: true),
                    Status = table.Column<string>(type: "nvarchar(20)", maxLength: 20, nullable: false),
                    MatchedInvoiceId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    ReceivedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_BankTransactions", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_BankTransactions_BankReference",
                schema: "billing",
                table: "BankTransactions",
                column: "BankReference",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_BankTransactions_Status",
                schema: "billing",
                table: "BankTransactions",
                column: "Status");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "BankTransactions",
                schema: "billing");

            migrationBuilder.DropColumn(
                name: "BankTransactionId",
                schema: "billing",
                table: "Payments");

            migrationBuilder.AddColumn<string>(
                name: "PaymentNote",
                schema: "billing",
                table: "Invoices",
                type: "nvarchar(max)",
                nullable: true);
        }
    }
}
