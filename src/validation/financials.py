from src.schemas.output import FinancialResolution

class FinancialValidator:
    @staticmethod
    def validate_totals(financials: FinancialResolution) -> bool:
        # Check if values are not negative
        if financials.item_total_brl < 0 or financials.freight_total_brl < 0 or financials.payment_total_brl < 0:
            return False
            
        # Ensure values don't have more than 2 decimal places (float precision issues might occur, so check rounding)
        if round(financials.item_total_brl, 2) != financials.item_total_brl:
            return False
            
        return True
