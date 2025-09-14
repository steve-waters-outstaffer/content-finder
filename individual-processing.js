// Individual URL processing function
const handleProcessUrl = async (url) => {
    if (processingUrls.has(url)) return; // Already processing

    setProcessingUrls(prev => new Set([...prev, url]));
    setError('');

    try {
        // Step 1: Scrape the URL
        console.log(`🔄 Processing: ${url}`);
        
        const scrapeResponse = await fetch('http://localhost:5000/api/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                urls: [url]
            })
        });

        if (!scrapeResponse.ok) {
            throw new Error(`Scraping failed: ${scrapeResponse.status}`);
        }

        const scrapeData = await scrapeResponse.json();
        const scrapeResult = scrapeData.results[0];

        if (!scrapeResult.success) {
            throw new Error(scrapeResult.error || 'Scraping failed');
        }

        console.log(`✅ Scraped: ${url}`);

        // Step 2: Analyze the content if scraping succeeded
        let analysisResult = null;
        if (scrapeResult.markdown) {
            console.log(`🤖 Analyzing: ${url}`);
            
            const analysisResponse = await fetch('http://localhost:5000/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: scrapeResult.markdown
                })
            });

            if (analysisResponse.ok) {
                analysisResult = await analysisResponse.json();
                analysisResult.source_url = url;
                console.log(`✅ Analyzed: ${url}`);
            } else {
                console.warn(`⚠️ Analysis failed for: ${url}`);
            }
        }

        // Store the results
        setProcessedResults(prev => ({
            ...prev,
            [url]: {
                scrape: scrapeResult,
                analysis: analysisResult,
                processedAt: new Date().toISOString()
            }
        }));

    } catch (err) {
        console.error(`❌ Failed to process ${url}:`, err);
        setProcessedResults(prev => ({
            ...prev,
            [url]: {
                error: err.message,
                processedAt: new Date().toISOString()
            }
        }));
    } finally {
        setProcessingUrls(prev => {
            const newSet = new Set(prev);
            newSet.delete(url);
            return newSet;
        });
    }
};

// Helper function to handle multiple URL processing
const handleProcessAllUrls = async () => {
    if (!results?.steps?.search?.results) return;
    
    const urls = results.steps.search.results.map(r => r.url);
    
    // Process URLs in parallel (max 3 at a time to avoid overwhelming)
    const batchSize = 3;
    for (let i = 0; i < urls.length; i += batchSize) {
        const batch = urls.slice(i, i + batchSize);
        await Promise.all(batch.map(url => handleProcessUrl(url)));
    }
};