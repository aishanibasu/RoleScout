from probe_feeds import go
for offset in [1260,1402,1405]:
 print(go((f'bny_tail{offset}',(f'https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=200,offset={offset},sortBy=POSTING_DATES_DESC',None))),flush=True)
