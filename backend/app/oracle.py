from .feed_common import job
from .ares import location
from .normalization import plain

class Oracle:
    def __init__(self,company,host,site):
        self.NAME=company;self.URL='https://'+host
        self.site=site;self.API=self.URL+'/hcmRestApi/resources/latest/'
    def fetch_snapshot(self,request):
        results,total,offset={},None,0
        page_size=199
        page_signatures=set()
        while total is None or offset<total:
            data=request(self.API+f'recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={self.site},limit={page_size},offset={offset},sortBy=POSTING_DATES_DESC').json()
            payload=data['items'][0];count=payload.get('TotalJobsCount');rows=payload.get('requisitionList')
            if type(count)is not int or not 0<count<30000 or not rows:raise ValueError('Invalid Oracle careers index')
            if total is not None and total!=count:raise ValueError('Oracle index changed during pagination')
            total=count
            signature=tuple(str(r['Id']) for r in rows)
            if signature in page_signatures:raise ValueError('Repeated Oracle page')
            page_signatures.add(signature)
            for r in rows:
                identifier=str(r['Id'])
                if not identifier.isdigit():raise ValueError('Invalid requisition ID')
                loc=location(r.get('PrimaryLocation',''))
                text=r.get('ShortDescriptionStr') or ''
                item=job(self.NAME,identifier,r['Title'],f'{self.URL}/hcmUI/CandidateExperience/en/sites/{self.site}/job/{identifier}',text,[loc] if loc else [],posted=r.get('PostedDate'),pending=True)
                results[identifier]=item
            if offset+page_size>=total:
                # Oracle's advertised total can include a few unavailable records.
                # Require an empty next page before accepting the terminal page.
                end=offset+page_size
                tail=request(self.API+f'recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={self.site},limit={page_size},offset={end},sortBy=POSTING_DATES_DESC').json()['items'][0]
                if tail.get('requisitionList') or tail.get('TotalJobsCount')!=total:
                    raise ValueError('Oracle terminal page could not be verified')
                break
            # Some Oracle feeds cap the requested size and shift rows at boundaries.
            # Offsets count feed positions, including unavailable records.
            offset+=page_size-20
        if not 0<=total-len(results)<=min(5,total//200):
            raise ValueError(f'Incomplete Oracle pages: {len(results)} unique jobs, expected {total}')
        for item in results.values():
            item['source_reported_total']=total
            item['source_index_unique_total']=len(results)
        return list(results.values())
    def fetch_detail(self,request,item):
        identifier=item['external_id']
        data=request(self.API+f'recruitingCEJobRequisitionDetails?onlyData=true&finder=ById;Id={identifier}').json()
        rows=data.get('items')
        if not rows or str(rows[0].get('Id'))!=identifier:raise ValueError('Oracle detail missing matching job')
        r=rows[0]
        text='\n'.join(r.get(k) or '' for k in ('ExternalDescriptionStr','ExternalQualificationsStr','ExternalResponsibilitiesStr'))
        if not text:raise ValueError('Oracle detail description missing')
        return dict(item,description=plain(text),details_pending=False,details_available=True)

bny=Oracle('BNY','eofe.fa.us2.oraclecloud.com','CX_3001')
bny.SCOPE='Public BNY career index. Full descriptions populate in background; a few unavailable feed records may be excluded.'
