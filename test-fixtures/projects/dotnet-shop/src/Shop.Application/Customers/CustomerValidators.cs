using FluentValidation;

namespace Shop.Application.Customers;

internal sealed class CreateCustomerRequestValidator : AbstractValidator<CreateCustomerRequest>
{
    public CreateCustomerRequestValidator()
    {
        RuleFor(r => r.Name).NotEmpty().MaximumLength(200);
        RuleFor(r => r.Email).NotEmpty().EmailAddress().MaximumLength(256);
    }
}

internal sealed class UpdateCustomerRequestValidator : AbstractValidator<UpdateCustomerRequest>
{
    public UpdateCustomerRequestValidator()
    {
        RuleFor(r => r.Name).NotEmpty().MaximumLength(200);
    }
}
