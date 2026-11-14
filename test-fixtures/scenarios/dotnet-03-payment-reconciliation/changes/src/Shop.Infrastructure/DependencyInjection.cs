using System.Net;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Polly;
using Polly.Extensions.Http;
using Polly.Timeout;
using Shop.Application.Abstractions;
using Shop.Application.Reconciliation;
using Shop.Infrastructure.BackgroundJobs;
using Shop.Infrastructure.Banking;
using Shop.Infrastructure.Messaging;
using Shop.Infrastructure.Payments;
using Shop.Infrastructure.Persistence;
using Shop.Infrastructure.Persistence.Repositories;

namespace Shop.Infrastructure;

public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddDbContext<ShopDbContext>(options => options.UseSqlServer(
            configuration.GetConnectionString("Shop"),
            sql =>
            {
                sql.EnableRetryOnFailure(maxRetryCount: 3);
                sql.MigrationsHistoryTable("__EFMigrationsHistory", ShopDbContext.Schema);
            }));

        services.AddScoped<IUnitOfWork>(sp => sp.GetRequiredService<ShopDbContext>());
        services.AddScoped<IInvoiceRepository, InvoiceRepository>();
        services.AddScoped<IPaymentRepository, PaymentRepository>();
        services.AddScoped<ICustomerRepository, CustomerRepository>();
        services.AddScoped<IBankTransactionRepository, BankTransactionRepository>();
        services.AddScoped<IEventPublisher, OutboxEventPublisher>();

        services.AddOptions<PaymentGatewayOptions>()
            .Bind(configuration.GetSection(PaymentGatewayOptions.SectionName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddHttpClient<IPaymentGateway, PaymentGatewayClient>((sp, http) =>
            {
                var options = sp.GetRequiredService<IOptions<PaymentGatewayOptions>>().Value;
                http.BaseAddress = options.BaseUrl;
                http.Timeout = TimeSpan.FromSeconds(options.OverallTimeoutSeconds);
                http.DefaultRequestHeaders.Add("X-Merchant-Id", options.MerchantId);
            })
            .AddPolicyHandler(RetryPolicy())
            .AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(TimeSpan.FromSeconds(10)));

        services.AddOptions<OverdueNotifierOptions>()
            .Bind(configuration.GetSection(OverdueNotifierOptions.SectionName));
        services.AddHostedService<OverdueInvoiceNotifier>();

        services.AddOptions<ReconciliationOptions>()
            .Bind(configuration.GetSection(ReconciliationOptions.SectionName));
        services.AddSingleton<ReconciliationCache>();
        services.AddTransient<IBankApiClient, BankApiClient>();
        services.AddHostedService<BankStatementImportWorker>();

        return services;
    }

    // Outer policy: retries transient failures (5xx, 408, 429 and per-try timeouts) with
    // exponential backoff + jitter. Charges are safe to retry because they carry an Idempotency-Key.
    private static IAsyncPolicy<HttpResponseMessage> RetryPolicy() =>
        HttpPolicyExtensions
            .HandleTransientHttpError()
            .Or<TimeoutRejectedException>()
            .OrResult(response => response.StatusCode == HttpStatusCode.TooManyRequests)
            .WaitAndRetryAsync(
                retryCount: 3,
                attempt => TimeSpan.FromMilliseconds(200 * Math.Pow(2, attempt))
                           + TimeSpan.FromMilliseconds(Random.Shared.Next(0, 100)));
}
