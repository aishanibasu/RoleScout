from probe_feeds import go
import concurrent.futures
url='https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=100,offset={offset},sortBy=POSTING_DATES_DESC'
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for r in pool.map(go,[(f'bny_sort{o}',(url.format(offset=o),None)) for o in [0,100]]):print(r,flush=True)
