#pydantic DHR invoice generator
'''Trying to use Pydantic to validate pieces of equipment read from a CSV and then generate an invoice'''

import pydantic
from pydantic_core import PydanticCustomError
from pydantic_extra_types.mac_address import MacAddress
from pydantic import ValidationError, ConfigDict, Field as PydanticField, AliasChoices, IPvAnyAddress
from typing import Optional, List, Generator, Dict, Any, Annotated
from icecream import ic
from easygui import *
import csv
import pandas as pd
from datetime import datetime

class CostInformation:
    PRICE_DICT: Dict[str, float] = {
        'MA4500ifx' : 1450.50,
        'M5526cdw' : 985.50,
        'MZ4000i' : 7170.00,
        'P2040dw' : 683.63,
        'TASKalfa 2554ci' : 7970.00,
        'MA4000cix' : 1807.57,
        'ECOSYS M2540dw' : 1200.00,
        'M2635dw' : 1200.00
    }
    total_cost_of_machines: float = 0
    total_monthly_payment:float = 0
    copiers: List = []
    FIELDS: List[str] = []
    current_date = pd.to_datetime(datetime.now())
    
class ValidationResults:
    passed: List = []
    failed: List = []

class Equipment(pydantic.BaseModel):
    model_config  = ConfigDict(protected_namespaces=(),
                            from_attributes=True,
                            populate_by_name=True,
                            str_strip_whitespace=True)

    equipment_number: Annotated[int, PydanticField(validation_alias=AliasChoices("Equipment number"))]
    serial_number: Annotated[str, PydanticField(validation_alias=AliasChoices("Serial number"))]
    item_desc: Annotated[str, PydanticField(validation_alias=AliasChoices("Item desc."))]
    customer_name: Annotated[str, PydanticField(validation_alias=AliasChoices("Customer name"))]
    make: Annotated[str, PydanticField(validation_alias=AliasChoices("Make"))]
    model: Annotated[str, PydanticField(validation_alias=AliasChoices("Model"))]
    address: Annotated[str, PydanticField(validation_alias=AliasChoices("Address"))]
    city: Annotated[str, PydanticField(validation_alias=AliasChoices("City"))]
    state: Annotated[str, PydanticField(validation_alias=AliasChoices("State"))]
    zip: Annotated[Optional[str], PydanticField(validation_alias=AliasChoices("Zip"))]
    location: Annotated[str, PydanticField(validation_alias=AliasChoices("Location"))]
    cost_center: Annotated[Optional[str], None] = None
    ip_address: Annotated[Optional[IPvAnyAddress], PydanticField(validation_alias=AliasChoices("IP address"))]
    mac_address: Annotated[Optional[MacAddress], PydanticField(validation_alias=AliasChoices("MAC address"))] 
    install_date: Annotated[str, PydanticField(validation_alias=AliasChoices("Install date"))]
    lease_end_date: Annotated[Optional[str], None] = None
    model_price: Annotated[Optional[float], None] = None
    monthly_payment: Annotated[Optional[float], None] = None
    
    @pydantic.field_validator('location')
    @classmethod
    def check_if_cost_center_exists(cls, value):
        '''Checks if the location data for the given equipment has a cost center.'''
        if 'CC:' not in value:
            raise PydanticCustomError(
                'equipment_missing_cost_center',
                f'Equipment is missing its cost center.'
            )
        return value
    
    @pydantic.field_validator('model')
    @classmethod
    def check_if_model_in_price_dict(cls, value):
        '''Checks if the model has a price defined.'''
        if value not in CostInformation.PRICE_DICT.keys():
            raise PydanticCustomError(
                'model_missing_price',
                f'Model has no price in PRICE_DICT. Model: {value}'
            )
        return value

def equipment_row_generator() -> Generator:
    input_csv: str = fileopenbox(msg = 'Select the input file. Must be a .csv', default='*.csv', filetypes = ['*.csv'])
    if not input_csv:
        print('No input file selected.')
        exit()    
    with open(input_csv, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            yield row

def write_invoice_to_csv() -> None:
    '''Outputs a formatted CSV as an accompanying file to DHR's monthly lease invoice.'''
    C = CostInformation
    out_file: str = filesavebox('Select output filename and location. Must be a csv.', default='*.csv', filetypes = ['*.csv'])
    if not out_file:
        print('No output file selected.')
        exit()    
    with open(out_file, 'w', newline = '') as output:
        if not C.FIELDS:
            for field in dict(C.copiers[0]).keys(): 
                C.FIELDS.append(field)
        writer = csv.DictWriter(output, fieldnames = C.FIELDS) #get back to this!
        list_writer = csv.writer(output)
        writer.writeheader()
        for copier in C.copiers:
            if copier.lease_end_date < CostInformation.current_date:
                print(f"MDS {copier.equipment_number}'s lease has ended.")
            else:
                writer.writerow(dict(copier))
        list_writer.writerow([])
        list_writer.writerow([])

        writer.writerow(
                        {
                            'equipment_number' : 'Total due this month:',
                            'serial_number' : f'${round((C.total_monthly_payment * 1.0825), 2)}',
                            'install_date' : 'Subtotal: ',
                            'model_price' : f'${round((C.total_cost_of_machines), 2)}',
                            'monthly_payment' : f'${round(C.total_monthly_payment, 2)}'
                        }
                        )
        writer.writerow(
                        {
                            'install_date' : 'Tax:',
                            'model_price' : f'${round((C.total_cost_of_machines * 0.0825))}',
                            'monthly_payment' : f'${round((C.total_monthly_payment * 0.0825), 2)}'
                        }
                        )
        writer.writerow(
                        {
                            'install_date' : 'Total: ',
                            'model_price' : f'${round((C.total_cost_of_machines * 1.0825), 2)}',
                            'monthly_payment' : f'${round((C.total_monthly_payment * 1.0825), 2)}'
                        }
                        )

def attempt_fix_machines(list) -> None:
    _corrected_amount: int = 0
    for machine in list:
        try:
            if not machine['IP address'] or machine['IP address'] == '':
                machine['IP address'] = '0.0.0.0'
            if not machine['MAC address'] or machine['MAC address'] == '':
                machine['MAC address'] = '00:00:00:00:00:00'
            if machine['Model'] in CostInformation.PRICE_DICT.keys():
                CostInformation.copiers.append(Equipment(**machine))
                _corrected_amount += 1
        except ValidationError as e:
            ic(e)
            ic(machine['Equipment number'])
    print(f'Corrected {_corrected_amount} machines!')

def main() -> None:
    '''Main Function'''
    equip_gen = equipment_row_generator()
   
    for item in equip_gen:    #iterate through the generator that is fed from the input CSV. Machines get added to a 'Pass' list and a 'Fail' list.
        try:
            CostInformation.copiers.append(Equipment(**item))
            ValidationResults.passed.append(item)
        except ValidationError as e:
            ic(item['Equipment number'])
            ValidationResults.failed.append(item)
    
    #try to fix machines that failed validation with this function so they can be added to the invoice
    if len(ValidationResults.failed) > 0:
        attempt_fix_machines((ValidationResults.failed))

    for copier in CostInformation.copiers:
        split_location = copier.location.split()
        try:
            cost_center_index = split_location.index('CC:')
        except Exception as e:
            if ccbox(msg=f'Check CC for MDS {copier.equipment_number}', title=' ', choices=('[O]k', '[Q]uit'), image=None, default_choice='Ok', cancel_choice='Quit'):
                ic(e)
                ic(f'MDS: {copier.equipment_number}')
            else:
                quit()
        copier.cost_center = split_location[cost_center_index + 1]
        copier.model_price = CostInformation.PRICE_DICT[copier.model]
        copier.lease_end_date = pd.to_datetime(copier.install_date) + pd.DateOffset(months=60)
        copier.monthly_payment = round((copier.model_price / 60), 2)
        if copier.lease_end_date > CostInformation.current_date:
            CostInformation.total_cost_of_machines += copier.model_price
            CostInformation.total_monthly_payment += round((copier.model_price / 60), 2)

    write_invoice_to_csv()
    print('Finished!')
    return

if __name__ == '__main__':
    main()