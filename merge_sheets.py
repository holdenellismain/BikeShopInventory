import pandas as pd
import csv

def isnumeric(value):
    '''
    Helper function to check if corrections are numbers or words such as 'delete'
    '''
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

#import excel sheets, sorted A->Z by Name
#using Name as the key since CloverIDs change and some items don't have product codes
jun = pd.read_excel('Inventory (Updated 6_12_2024).xlsx')
aug = pd.read_excel('Inventory (Updated 8_20_2024).xlsx')

to_delete = [] #list of items that need to be deleted
counting_error = [] #items with unexpected counting results

june_index = 0
for index, aug_row in aug.iterrows():
    if june_index > jun.shape[0] - 1:
        june_index = jun.shape[0] - 1 #avoid going out of range with new values at the end of the august list
    
    if jun.iloc[june_index,1] == aug_row['Name']:
        #rename varible for readability
        jun_corr = jun.iloc[june_index]['CORRECTION']
        aug_corr = aug_row['CORRECTION']
        #if someone says it should be deleted, correct count to 0 and delete manually
        if not isnumeric(jun_corr) or not isnumeric(aug_corr):
            aug.loc[index,'Quantity'] = 0
            to_delete.append(aug_row['Name'])
        #if both june and august have corrections
        elif (jun_corr == jun_corr)  and (aug_corr == aug_corr):
            #check if difference between inventory amounts and correction amounts matches
            corr_diff = int(jun_corr) - int(aug_corr)
            jun_count = int(jun.iloc[june_index]['Quantity']) 
            aug_count = int(aug_row['Quantity'])
            official_diff = jun_count - aug_count
            if corr_diff != official_diff:
                with open('counting_errors.csv','a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([aug_row['Name'],jun_count,aug_count,official_diff,jun_corr,aug_corr,corr_diff])
            aug.loc[index,'Quantity'] = int(aug_corr)
        #if only june has a corrrection
        elif (jun_corr == jun_corr):
            aug.loc[index,'Quantity'] = int(jun_corr)
        #if only august has a correction
        elif (aug_corr == aug_corr):
            aug.loc[index,'Quantity'] = int(aug_corr)
        #no correction needs to be made
        elif (jun_corr != jun_corr) and (aug_corr != aug_corr):
            pass
        else:
            print('ERROR: MISSING EDGE CASE')
        june_index += 1
    else:
        #if august sheet has a correction but item is not in June sheet
        aug_corr = aug_row['CORRECTION']
        if not isnumeric(aug_corr):
            aug.loc[index,'Quantity'] = 0
            to_delete.append('Delete', aug_row['Name'])
        elif (aug_corr == aug_corr):
            aug.loc[index,'Quantity'] = int(aug_corr)

#remove correction column so that sheet can be reimported
aug.drop('CORRECTION', axis=1, inplace=True)

#further correction information
duplicate_names = aug[aug['Name'].duplicated(keep=False)]['Name'].unique() #array of duplicate names
duplicate_codes = aug[aug['Product Code'].duplicated(keep=False)]['Product Code'].unique() #array of duplicate names

#text file for debug information
output = open('output.txt', 'w')
output.write('ITEMS TO BE DELETED\n')
for item in to_delete:
    output.write('\n' + str(item))
output.write('\n\nDUPLICATE NAMES\n')
for item in duplicate_names:
    output.write('\n' + str(item))
output.write('\n\nDUPLICATE PRODUCTIDS\n')
for item in duplicate_codes:
    output.write('\n' + str(item))
print('Output file written')

#print to excel
aug.to_excel('Corrected Inventory (9_13_2024).xlsx', index=False)
