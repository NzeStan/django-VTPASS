"""
REST API routes. Mount with ``path("api/vtpass/", include("vtpass.api.urls"))``.

Catalogue & helpers
    GET  catalog/categories/
    GET  catalog/services/?category=<identifier>
    GET  catalog/services/<service_id>/variations/   (?operator_id=&product_type_id=)
    GET  catalog/services/<service_id>/options/?name=<option>
    GET  networks/detect/?phone=<number>
    POST verify/                     any service: {service_id, billers_code, type}
    POST quote/                      price preview: fee, discount, cashback, amount payable

Products
    GET  airtime/networks/           POST airtime/
    GET  data/networks/              GET  data/plans/?network=mtn   POST data/
    GET  tv/providers/               GET  tv/<provider>/bouquets/   POST tv/verify/   POST tv/
    GET  electricity/discos/         POST electricity/verify/       POST electricity/
    GET  education/products/         POST education/jamb/verify/    POST education/
    GET  internet/providers/         POST internet/smile/verify/    POST internet/
    GET  insurance/plans/[?product=personal-accident-insurance]
    GET  insurance/options/<option>/?parent=   POST insurance/   POST insurance/personal-accident/
    GET  bank-transfer/banks/        POST bank-transfer/verify/     POST bank-transfer/
    GET  international/countries/    GET  international/product-types/?country=
    GET  international/operators/?country=&product_type_id=
    GET  international/variations/?operator_id=&product_type_id=           POST international/
    POST purchase/                   generic purchase for any service ID

Account
    GET  transactions/               GET transactions/<reference>/   POST transactions/<reference>/requery/
    GET  wallet/                     GET wallet/entries/
    GET/POST beneficiaries/          GET/PATCH/DELETE beneficiaries/<uid>/

Admin
    GET  merchant/balance/           GET reports/earnings/
    POST sms/send/                   GET sms/balance/
"""

from django.urls import path

from vtpass.api.views import (
    airtime,
    bank,
    cable,
    commission,
    data,
    education,
    electricity,
    insurance,
    international,
    internet,
    service,
    transaction,
    wallet,
)

app_name = "vtpass_api"

urlpatterns = [
    # catalogue & helpers
    path("catalog/categories/", service.CategoryListView.as_view(), name="categories"),
    path("catalog/services/", service.ServiceListView.as_view(), name="services"),
    path("catalog/services/<str:service_id>/variations/", service.VariationListView.as_view(), name="variations"),
    path("catalog/services/<str:service_id>/options/", service.OptionListView.as_view(), name="options"),
    path("networks/detect/", service.DetectNetworkView.as_view(), name="detect-network"),
    path("verify/", service.VerifyView.as_view(), name="verify"),
    path("quote/", service.QuoteView.as_view(), name="quote"),
    path("purchase/", service.GenericPurchaseView.as_view(), name="purchase"),
    # airtime & data
    path("airtime/networks/", airtime.AirtimeNetworksView.as_view(), name="airtime-networks"),
    path("airtime/", airtime.AirtimePurchaseView.as_view(), name="airtime"),
    path("data/networks/", data.DataNetworksView.as_view(), name="data-networks"),
    path("data/plans/", data.DataPlansView.as_view(), name="data-plans"),
    path("data/", data.DataPurchaseView.as_view(), name="data"),
    # tv
    path("tv/providers/", cable.TVProvidersView.as_view(), name="tv-providers"),
    path("tv/<str:provider>/bouquets/", cable.TVBouquetsView.as_view(), name="tv-bouquets"),
    path("tv/verify/", cable.TVVerifyView.as_view(), name="tv-verify"),
    path("tv/", cable.TVPurchaseView.as_view(), name="tv"),
    # electricity
    path("electricity/discos/", electricity.DiscoListView.as_view(), name="electricity-discos"),
    path("electricity/verify/", electricity.MeterVerifyView.as_view(), name="electricity-verify"),
    path("electricity/", electricity.ElectricityPurchaseView.as_view(), name="electricity"),
    # education
    path("education/products/", education.EducationProductsView.as_view(), name="education-products"),
    path("education/jamb/verify/", education.JambVerifyView.as_view(), name="jamb-verify"),
    path("education/", education.EducationPurchaseView.as_view(), name="education"),
    # internet
    path("internet/providers/", internet.InternetProvidersView.as_view(), name="internet-providers"),
    path("internet/smile/verify/", internet.SmileVerifyView.as_view(), name="smile-verify"),
    path("internet/", internet.InternetPurchaseView.as_view(), name="internet"),
    # insurance
    path("insurance/plans/", insurance.InsurancePlansView.as_view(), name="insurance-plans"),
    path("insurance/options/<str:option>/", insurance.InsuranceOptionsView.as_view(), name="insurance-options"),
    path("insurance/", insurance.MotorInsurancePurchaseView.as_view(), name="insurance"),
    path("insurance/personal-accident/", insurance.PersonalAccidentPurchaseView.as_view(),
         name="insurance-personal-accident"),
    # bank transfer
    path("bank-transfer/banks/", bank.BankListView.as_view(), name="banks"),
    path("bank-transfer/verify/", bank.BankAccountVerifyView.as_view(), name="bank-verify"),
    path("bank-transfer/", bank.BankTransferView.as_view(), name="bank-transfer"),
    # international airtime
    path("international/countries/", international.CountriesView.as_view(), name="intl-countries"),
    path("international/product-types/", international.ProductTypesView.as_view(), name="intl-product-types"),
    path("international/operators/", international.OperatorsView.as_view(), name="intl-operators"),
    path("international/variations/", international.InternationalVariationsView.as_view(), name="intl-variations"),
    path("international/", international.InternationalPurchaseView.as_view(), name="international"),
    # account
    path("transactions/", transaction.TransactionListView.as_view(), name="transactions"),
    path("transactions/<str:reference>/", transaction.TransactionDetailView.as_view(), name="transaction-detail"),
    path(
        "transactions/<str:reference>/requery/",
        transaction.TransactionRequeryView.as_view(),
        name="transaction-requery",
    ),
    path("wallet/", wallet.WalletView.as_view(), name="wallet"),
    path("wallet/entries/", wallet.WalletEntryListView.as_view(), name="wallet-entries"),
    path("beneficiaries/", wallet.BeneficiaryListCreateView.as_view(), name="beneficiaries"),
    path("beneficiaries/<uuid:uid>/", wallet.BeneficiaryDetailView.as_view(), name="beneficiary-detail"),
    # admin
    path("merchant/balance/", service.MerchantBalanceView.as_view(), name="merchant-balance"),
    path("reports/earnings/", commission.EarningsReportView.as_view(), name="earnings"),
    path("sms/send/", service.SMSSendView.as_view(), name="sms-send"),
    path("sms/balance/", service.SMSBalanceView.as_view(), name="sms-balance"),
]
