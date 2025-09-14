import os
import json
from firecrawl import Firecrawl

def scrape_job_urls():
    """
    Crawls job board websites to discover and save URLs for individual job postings.
    """
    # 1. --- Configuration ---

    # Get API key from environment variable for security
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY environment variable not set. Please set it before running.")

    # List of starting points for our crawl
    STARTING_URLS = [
        'https://www.seek.com.au/technology-jobs',
        'https://au.indeed.com/q-information-technology-jobs.html',
        'https://www.linkedin.com/jobs/search?keywords=Technology&location=Australia'
    ]

    # Parameters for the crawl job.
    # We set a limit to avoid excessively long or expensive crawls.
    # Increase this number to get more URLs.
    CRAWL_LIMIT_PER_SITE = 100

    # 2. --- Initialization ---

    firecrawl = Firecrawl(api_key=api_key)
    all_job_urls = []

    print("Starting crawl to discover job posting URLs...")

    # 3. --- Main Crawl Loop ---

    for url in STARTING_URLS:
        print(f"\nCrawling starting from: {url}")

        try:
            # Using the blocking `crawl` method for simplicity in a script.
            # It waits for the job to complete.
            crawl_result = firecrawl.crawl(
                url=url,
                params={
                    'crawlerOptions': {
                        'limit': CRAWL_LIMIT_PER_SITE,
                        # We only need the URLs, so we can disable screenshots to save credits.
                        'generateImgCaptions': False
                    },
                    # We don't need the page content for this step, just the URLs found.
                    # Setting formats to an empty list might reduce cost/processing.
                    'pageOptions': {
                        'onlyMainContent': True
                    }
                }
            )

            if not crawl_result:
                print(f"No data returned from crawl for {url}")
                continue

            # 4. --- Filtering for Job URLs ---

            found_count = 0
            for item in crawl_result:
                source_url = item.get('metadata', {}).get('sourceURL')
                if not source_url:
                    continue

                # Simple filters to identify URLs that are likely job postings.
                # You might need to adjust these patterns.
                is_job_posting = False
                if 'seek.com.au/job/' in source_url:
                    is_job_posting = True
                if 'indeed.com/viewjob' in source_url or 'indeed.com/rc/clk' in source_url:
                    is_job_posting = True
                if 'linkedin.com/jobs/view/' in source_url:
                    is_job_posting = True

                if is_job_posting:
                    all_job_urls.append(source_url)
                    found_count += 1

            print(f"Found {found_count} potential job posting URLs from {url.split('//')[1].split('/')[0]}.")

        except Exception as e:
            print(f"An error occurred while crawling {url}: {e}")

    # 5. --- Save the Results ---

    # Remove duplicates by converting to a set and back to a list
    unique_job_urls = list(set(all_job_urls))

    print(f"\nTotal unique job URLs found: {len(unique_job_urls)}")

    output_filename = 'job_urls.json'
    with open(output_filename, 'w') as f:
        json.dump(unique_job_urls, f, indent=2)

    print(f"Successfully saved URLs to {output_filename}")
    print("You can now use this file as the input for the next extraction script.")


if __name__ == "__main__":
    scrape_job_urls()