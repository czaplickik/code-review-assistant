using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Shop.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class AddPaymentReference : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "ProviderReference",
                schema: "billing",
                table: "Payments",
                type: "nvarchar(64)",
                maxLength: 64,
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "FeeAmount",
                schema: "billing",
                table: "Payments",
                type: "decimal(18,2)",
                precision: 18,
                scale: 2,
                nullable: true);

            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "SettledAt",
                schema: "billing",
                table: "Payments",
                type: "datetimeoffset",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "ReconciliationStatus",
                schema: "billing",
                table: "Payments",
                type: "int",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.CreateIndex(
                name: "IX_Payments_ProviderReference",
                schema: "billing",
                table: "Payments",
                column: "ProviderReference",
                filter: "[ProviderReference] IS NOT NULL");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_Payments_ProviderReference",
                schema: "billing",
                table: "Payments");

            migrationBuilder.DropColumn(
                name: "ProviderReference",
                schema: "billing",
                table: "Payments");

            migrationBuilder.DropColumn(
                name: "FeeAmount",
                schema: "billing",
                table: "Payments");

            migrationBuilder.DropColumn(
                name: "SettledAt",
                schema: "billing",
                table: "Payments");

            migrationBuilder.DropColumn(
                name: "ReconciliationStatus",
                schema: "billing",
                table: "Payments");
        }
    }
}
