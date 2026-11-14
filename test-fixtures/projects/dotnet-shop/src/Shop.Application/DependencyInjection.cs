using FluentValidation;
using Microsoft.Extensions.DependencyInjection;
using Shop.Application.Customers;

namespace Shop.Application;

public static class DependencyInjection
{
    public static IServiceCollection AddApplication(this IServiceCollection services)
    {
        var assembly = typeof(DependencyInjection).Assembly;

        services.AddMediatR(cfg => cfg.RegisterServicesFromAssembly(assembly));
        services.AddValidatorsFromAssembly(assembly, includeInternalTypes: true);

        services.AddScoped<ICustomerService, CustomerService>();

        return services;
    }
}
