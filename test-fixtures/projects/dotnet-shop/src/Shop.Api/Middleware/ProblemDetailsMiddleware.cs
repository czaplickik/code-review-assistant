using FluentValidation;
using Microsoft.AspNetCore.Mvc;
using Shop.Domain.Exceptions;

namespace Shop.Api.Middleware;

/// <summary>
/// Translates <see cref="DomainException"/>s and validation failures into RFC 7807 problem details.
/// Anything else propagates to <c>UseExceptionHandler</c> and becomes a generic 500.
/// </summary>
public sealed class ProblemDetailsMiddleware(RequestDelegate next, ILogger<ProblemDetailsMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context, IProblemDetailsService problemDetailsService)
    {
        try
        {
            await next(context);
        }
        catch (ValidationException ex) when (!context.Response.HasStarted)
        {
            var problem = new ValidationProblemDetails(
                ex.Errors.GroupBy(e => e.PropertyName).ToDictionary(g => g.Key, g => g.Select(e => e.ErrorMessage).ToArray()))
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Validation failed",
            };

            await WriteAsync(context, problemDetailsService, problem);
        }
        catch (DomainException ex) when (!context.Response.HasStarted)
        {
            var status = ex switch
            {
                NotFoundException => StatusCodes.Status404NotFound,
                InvalidInvoiceStateException or DuplicateCustomerException => StatusCodes.Status409Conflict,
                CurrencyMismatchException or InvalidCurrencyException or InvalidPaymentAmountException => StatusCodes.Status422UnprocessableEntity,
                PaymentDeclinedException => StatusCodes.Status402PaymentRequired,
                _ => StatusCodes.Status400BadRequest,
            };

            logger.LogInformation("Domain rule violated ({Code}): {Message}", ex.Code, ex.Message);

            var problem = new ProblemDetails { Status = status, Title = ex.Message };
            problem.Extensions["code"] = ex.Code;

            await WriteAsync(context, problemDetailsService, problem);
        }
    }

    private static async Task WriteAsync(HttpContext context, IProblemDetailsService service, ProblemDetails problem)
    {
        context.Response.StatusCode = problem.Status ?? StatusCodes.Status400BadRequest;
        await service.WriteAsync(new ProblemDetailsContext { HttpContext = context, ProblemDetails = problem });
    }
}
