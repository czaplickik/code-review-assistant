using FluentValidation;

namespace Shop.Application.Customers;

internal sealed class CreateCustomerNoteRequestValidator : AbstractValidator<CreateCustomerNoteRequest>
{
    public CreateCustomerNoteRequestValidator()
    {
        RuleFor(r => r.Body).NotEmpty().MaximumLength(4000);
    }
}

internal sealed class UpdateCustomerNoteRequestValidator : AbstractValidator<UpdateCustomerNoteRequest>
{
    public UpdateCustomerNoteRequestValidator()
    {
        RuleFor(r => r.Body).NotEmpty().MaximumLength(4000);
    }
}
