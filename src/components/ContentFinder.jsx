// src/components/ContentFinder.jsx
import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    TextField,
    Button,
    Typography,
    Alert,
    CircularProgress,
    Chip,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Divider,
    Stack,
    Paper,
    Checkbox,
    FormControlLabel,
    Select,
    MenuItem,
    FormControl,
    InputLabel
} from '@mui/material';
import {
    Search as SearchIcon,
    ExpandMore as ExpandMoreIcon,
    Link as LinkIcon,
    TrendingUp as TrendingUpIcon,
    Psychology as PsychologyIcon,
    Assignment as AssignmentIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../theme';

const ContentFinder = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchLimit, setSearchLimit] = useState(5);
    const [isLoading, setIsLoading] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const [processingUrls, setProcessingUrls] = useState(new Set());
    const [processedResults, setProcessedResults] = useState({});
    const [processingStatus, setProcessingStatus] = useState({}); // Track individual URL status
    const [sourceRatings, setSourceRatings] = useState({}); // Track source ratings
    const [contentRatings, setContentRatings] = useState({}); // Track content ratings
    const [selectedUrls, setSelectedUrls] = useState(new Set());
    const [isSynthesizing, setIsSynthesizing] = useState(false);
    const [synthesisResult, setSynthesisResult] = useState(null);

    // Curated search terms for quick selection
    const curatedTerms = [
        'SMB hiring challenges 2025',
        'APAC talent recruitment trends',
        'EOR global hiring benefits',
        'AI in staffing industry'
    ];

    const handleSearch = async () => {
        if (!searchQuery.trim()) {
            setError('Please enter a search query');
            return;
        }

        setIsLoading(true);
        setError('');
        setResults(null);
        setProcessedResults({});
        setSelectedUrls(new Set());
        setSynthesisResult(null);


        try {
            const response = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: searchQuery,
                    limit: searchLimit
                })
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const searchData = await response.json();

            setResults({
                query: searchQuery,
                steps: {
                    search: searchData
                }
            });
        } catch (err) {
            setError(`Failed to search: ${err.message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCuratedTermClick = (term) => {
        setSearchQuery(term);
    };

    const handleSourceRating = (url, rating) => {
        setSourceRatings(prev => ({ ...prev, [url]: rating }));
        console.log(`⭐ Source rated: ${new URL(url).hostname} = ${rating} stars`);
        // TODO: Save to Firestore
    };

    const handleContentRating = (url, rating) => {
        setContentRatings(prev => ({ ...prev, [url]: rating }));
        console.log(`🤖 Analysis rated: ${new URL(url).hostname} = ${rating} stars`);
        // TODO: Save to Firestore
    };

    const renderStarRating = (currentRating, onRate, label) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="caption">
                {label}:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.2 }}>
                {[1, 2, 3, 4, 5].map(star => (
                    <Typography
                        key={star}
                        onClick={() => onRate(star)}
                        sx={{
                            cursor: 'pointer',
                            fontSize: '16px',
                            '&:hover': {
                                opacity: 0.7,
                                transform: 'scale(1.1)'
                            },
                            transition: 'all 0.2s'
                        }}
                    >
                        {star <= (currentRating || 0) ? '⭐' : '☆'}
                    </Typography>
                ))}
            </Box>
            <Typography variant="caption" color="text.secondary">
                {currentRating ? `(${currentRating}/5)` : '(Optional)'}
            </Typography>
        </Box>
    );

    const handleProcessUrl = async (url) => {
        if (processingUrls.has(url)) return;

        setProcessingUrls(prev => new Set([...prev, url]));
        setProcessingStatus(prev => ({ ...prev, [url]: 'scraping' }));
        setError('');

        try {
            const scrapeResponse = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: [url] })
            });

            if (!scrapeResponse.ok) throw new Error(`Scraping failed: ${scrapeResponse.status}`);
            const scrapeData = await scrapeResponse.json();
            const scrapeResult = scrapeData.results[0];
            if (!scrapeResult.success) throw new Error(scrapeResult.error || 'Scraping failed');

            setProcessingStatus(prev => ({ ...prev, [url]: 'analyzing' }));

            let analysisResult = null;
            if (scrapeResult.markdown) {
                const analysisResponse = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: scrapeResult.markdown })
                });

                if (analysisResponse.ok) {
                    analysisResult = await analysisResponse.json();
                    analysisResult.source_url = url;
                }
            }

            setProcessedResults(prev => ({
                ...prev,
                [url]: {
                    scrape: scrapeResult,
                    analysis: analysisResult,
                    processedAt: new Date().toISOString()
                }
            }));
            setProcessingStatus(prev => ({ ...prev, [url]: 'completed' }));
        } catch (err) {
            setProcessedResults(prev => ({
                ...prev,
                [url]: { error: err.message, processedAt: new Date().toISOString() }
            }));
            setProcessingStatus(prev => ({ ...prev, [url]: 'error' }));
        } finally {
            setProcessingUrls(prev => {
                const newSet = new Set(prev);
                newSet.delete(url);
                return newSet;
            });
        }
    };

    const handleUrlSelection = (url, isSelected) => {
        const newSelectedUrls = new Set(selectedUrls);
        if (isSelected) {
            newSelectedUrls.add(url);
        } else {
            newSelectedUrls.delete(url);
        }
        setSelectedUrls(newSelectedUrls);
    };

    const handleSynthesizeSelected = async () => {
        if (selectedUrls.size === 0) {
            setError('Please select at least one article to synthesize.');
            return;
        }

        setIsSynthesizing(true);
        setError('');
        setSynthesisResult(null);

        try {
            const scrapeResponse = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: Array.from(selectedUrls) }),
            });

            if (!scrapeResponse.ok) throw new Error('Failed to scrape content for synthesis.');

            const scrapeData = await scrapeResponse.json();
            const successfulScrapes = scrapeData.results.filter(r => r.success && r.markdown);

            if (successfulScrapes.length === 0) {
                throw new Error('Could not retrieve content from any of the selected URLs.');
            }

            const synthesisResponse = await fetch('https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/synthesize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: searchQuery,
                    contents: successfulScrapes.map(s => ({
                        url: s.url,
                        title: s.title,
                        markdown: s.markdown
                    }))
                }),
            });

            if (!synthesisResponse.ok) throw new Error('The AI failed to synthesize the article.');

            const synthesisData = await synthesisResponse.json();
            setSynthesisResult(synthesisData);

        } catch (err) {
            setError(`Synthesis failed: ${err.message}`);
        } finally {
            setIsSynthesizing(false);
        }
    };


    const renderSearchResults = () => {
        if (!results?.steps?.search?.results) return null;
        const searchResults = results.steps.search.results;

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography variant="h6" gutterBottom>
                            <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Search Results ({searchResults.length} found)
                        </Typography>
                        <Button
                            variant="contained"
                            color="secondary"
                            disabled={selectedUrls.size === 0 || isSynthesizing}
                            onClick={handleSynthesizeSelected}
                            startIcon={isSynthesizing ? <CircularProgress size={16} /> : <PsychologyIcon />}
                        >
                            {isSynthesizing ? 'Synthesizing...' : `Synthesize (${selectedUrls.size}) Articles`}
                        </Button>
                    </Box>

                    {searchResults.map((result, index) => {
                        const isProcessing = processingUrls.has(result.url);
                        const processedData = processedResults[result.url];
                        const hasBeenProcessed = !!processedData;
                        const currentStatus = processingStatus[result.url];

                        return (
                            <Paper
                                key={index}
                                elevation={0}
                                sx={{
                                    p: 2,
                                    mb: 1,
                                    border: `2px solid ${hasBeenProcessed ? (processedData.error ? CustomColors.DarkRed : CustomColors.SecretGarden) : CustomColors.UIGrey300}`,
                                    borderRadius: 2,
                                    backgroundColor: 'white'
                                }}
                            >
                                <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                                    <Checkbox
                                        checked={selectedUrls.has(result.url)}
                                        onChange={(e) => handleUrlSelection(result.url, e.target.checked)}
                                        sx={{ mt: 1.5, mr: 1 }}
                                    />
                                    <Box sx={{ flex: 1 }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                            <Box sx={{ flex: 1 }}>
                                                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                                    {result.title || `Search Result ${index + 1}`}
                                                </Typography>
                                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                    {result.description || 'No description available'}
                                                </Typography>
                                                <Typography
                                                    variant="caption"
                                                    sx={{ color: CustomColors.DeepSkyBlue, textDecoration: 'underline', cursor: 'pointer' }}
                                                    onClick={() => window.open(result.url, '_blank')}
                                                >
                                                    <LinkIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                                    {result.url}
                                                </Typography>
                                                <Box sx={{ mt: 1 }}>
                                                    {renderStarRating(sourceRatings[result.url], (rating) => handleSourceRating(result.url, rating), 'Source Quality')}
                                                </Box>
                                                {(isProcessing || hasBeenProcessed) && (
                                                    <Box sx={{ mt: 1 }}>
                                                        {isProcessing && (
                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                <CircularProgress size={16} />
                                                                <Typography variant="caption" color="primary">
                                                                    {currentStatus === 'scraping' && '📄 Scraping content...'}
                                                                    {currentStatus === 'analyzing' && '🤖 Analyzing with AI...'}
                                                                </Typography>
                                                            </Box>
                                                        )}
                                                        {hasBeenProcessed && !isProcessing && (
                                                            <Box>
                                                                {processedData.error ? (
                                                                    <Typography variant="caption" color="error">
                                                                        ❌ Failed: {processedData.error}
                                                                    </Typography>
                                                                ) : (
                                                                    <Typography variant="caption" color="success.main">
                                                                        ✅ Processed: Scraped {processedData.scrape?.success ? '✓' : '✗'} | Analyzed {processedData.analysis?.success ? '✓' : '✗'}
                                                                    </Typography>
                                                                )}
                                                            </Box>
                                                        )}
                                                    </Box>
                                                )}
                                            </Box>
                                            <Box sx={{ ml: 2 }}>
                                                <Button
                                                    variant={hasBeenProcessed ? "outlined" : "contained"}
                                                    color={hasBeenProcessed ? "secondary" : "primary"}
                                                    size="small"
                                                    onClick={() => handleProcessUrl(result.url)}
                                                    disabled={isProcessing}
                                                    sx={{ minWidth: 100 }}
                                                >
                                                    {isProcessing ? (currentStatus === 'scraping' ? 'Scraping...' : 'Analyzing...') : hasBeenProcessed ? (processedData.error ? 'Retry' : 'Reprocess') : ('Process')}
                                                </Button>
                                            </Box>
                                        </Box>
                                    </Box>
                                </Box>
                            </Paper>
                        );
                    })}
                </CardContent>
            </Card>
        );
    };

    const renderAnalysis = () => {
        const analysisEntries = Object.entries(processedResults).filter(([, data]) => data.analysis?.success && !data.error);
        if (analysisEntries.length === 0) return null;
        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Individual AI Analysis ({analysisEntries.length} insights)
                    </Typography>
                    {analysisEntries.map(([url, data], index) => (
                        <Accordion key={url} defaultExpanded sx={{ mb: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                    Analysis for {new URL(url).hostname}
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        {data.scrape.title || `Article ${index + 1}`}
                                    </Typography>
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails sx={{ pt: 0 }}>
                                <Accordion defaultExpanded sx={{ mb: 1, boxShadow: 'none' }}>
                                    <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ bgcolor: CustomColors.AliceBlue, borderRadius: 1, mb: 1, '&.Mui-expanded': { minHeight: 48 } }}>
                                        <Typography variant="body2" fontWeight={FontWeight.SemiBold}>📄 AI Insights</Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Box sx={{ bgcolor: CustomColors.UIGrey100, p: 2, borderRadius: 1, whiteSpace: 'pre-wrap', mb: 2 }}>
                                            <Typography variant="body2">{data.analysis.analysis}</Typography>
                                        </Box>
                                        {renderStarRating(contentRatings[url], (rating) => handleContentRating(url, rating), 'Analysis Usefulness')}
                                    </AccordionDetails>
                                </Accordion>
                                <Accordion sx={{ boxShadow: 'none' }}>
                                    <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ bgcolor: CustomColors.UIGrey200, borderRadius: 1 }}>
                                        <Typography variant="body2" fontWeight={FontWeight.Medium}>📋 Source Content ({data.scrape.markdown?.length || 0} chars)</Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Typography variant="body2" sx={{ maxHeight: '300px', overflow: 'auto', bgcolor: CustomColors.UIGrey100, p: 2, borderRadius: 1, fontSize: '12px', color: CustomColors.UIGrey600 }}>
                                            {data.scrape.markdown ? data.scrape.markdown.substring(0, 2000) + (data.scrape.markdown.length > 2000 ? '...' : '') : 'No content available'}
                                        </Typography>
                                    </AccordionDetails>
                                </Accordion>
                            </AccordionDetails>
                        </Accordion>
                    ))}
                </CardContent>
            </Card>
        );
    };

    const renderSynthesisResult = () => {
        if (!synthesisResult) return null;

        // Helper function to render the LinkedIn post in a styled paper
        const renderLinkedInPost = (post) => {
            if (!post) return null;
            return (
                <Paper elevation={0} sx={{ p: 2, bgcolor: CustomColors.UIGrey100, mt: 1 }}>
                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold}>Angle: {post.angle}</Typography>
                    <Divider sx={{ my: 1 }} />
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', my: 2 }}>{post.text}</Typography>
                    <Typography variant="caption" color="text.secondary">{post.hashtags?.join(' ')}</Typography>
                </Paper>
            );
        };

        // Helper function to render the article and handle markdown titles
        const renderArticle = (articleText) => {
            if (!articleText) return <Typography>No article content available.</Typography>;

            // Split article into paragraphs and render them, converting "## Title" to a heading
            return articleText.split(/\\n\\n+/).map((paragraph, index) => {
                if (paragraph.startsWith('## ')) {
                    return <Typography key={index} variant="h5" sx={{ mt: 2, mb: 1 }}>{paragraph.replace('## ', '')}</Typography>
                }
                // Replace any other markdown for clean text
                const cleanParagraph = paragraph.replace(/(\*\*|##)/g, '');
                return <Typography key={index} paragraph>{cleanParagraph}</Typography>
            });
        };

        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    {/* Accordion for the Synthesized Article */}
                    <Accordion defaultExpanded>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            sx={{ bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}
                        >
                            <Typography variant="h6">
                                <AssignmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                                Synthesized Research Article
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 2 }}>
                            {renderArticle(synthesisResult.article)}
                        </AccordionDetails>
                    </Accordion>

                    {/* Accordion for the Strategic Insights */}
                    <Accordion defaultExpanded sx={{ mt: 2 }}>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            sx={{ bgcolor: CustomColors.AliceBlue, borderRadius: 1 }}
                        >
                            <Typography variant="h6">
                                <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                                Outstaffer Strategic Insights
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 2 }}>
                            {synthesisResult.outstaffer_analysis && (
                                <>
                                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold}>Relevance & Opportunity</Typography>
                                    <Typography variant="body2" color="text.secondary" paragraph>
                                        {synthesisResult.outstaffer_analysis.relevance_opportunity}
                                    </Typography>

                                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold}>Key Talking Point</Typography>
                                    <Typography variant="body2" color="text.secondary" paragraph>
                                        {synthesisResult.outstaffer_analysis.key_talking_point}
                                    </Typography>
                                </>
                            )}
                            {synthesisResult.linkedin_post && (
                                <>
                                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold}>LinkedIn Post Idea</Typography>
                                    {renderLinkedInPost(synthesisResult.linkedin_post)}
                                </>
                            )}
                        </AccordionDetails>
                    </Accordion>
                </CardContent>
            </Card>
        );
    };

    return (
        <Box sx={{ maxWidth: '100%' }}>
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h5" gutterBottom fontWeight={FontWeight.SemiBold}>
                        Quick Research Tool
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        Search any topic, scrape and analyze multiple sources, then synthesize findings into strategic content briefs.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, mb: 2, mt: 2 }}>
                        <TextField
                            fullWidth
                            variant="outlined"
                            label="Search Query"
                            placeholder="Enter search terms (e.g., 'SMB hiring trends 2025')"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                            disabled={isLoading}
                        />
                        <FormControl sx={{ minWidth: 120 }}>
                            <InputLabel>Results</InputLabel>
                            <Select
                                value={searchLimit}
                                label="Results"
                                onChange={(e) => setSearchLimit(e.target.value)}
                                disabled={isLoading}
                            >
                                {[1, 2, 3, 5, 7, 10].map(num => (
                                    <MenuItem key={num} value={num}>{num}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleSearch}
                            disabled={isLoading || !searchQuery.trim()}
                            sx={{ minWidth: 120 }}
                        >
                            {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Search'}
                        </Button>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Quick searches:
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {curatedTerms.map((term, index) => (
                                <Chip
                                    key={index}
                                    label={term}
                                    onClick={() => handleCuratedTermClick(term)}
                                    variant="outlined"
                                    size="medium"
                                    sx={{
                                        cursor: 'pointer',
                                        borderRadius: '20px',
                                        borderColor: CustomColors.DeepSkyBlue,
                                        color: CustomColors.DeepSkyBlue,
                                        fontWeight: FontWeight.Medium,
                                        '&:hover': {
                                            backgroundColor: CustomColors.AliceBlue,
                                            borderColor: CustomColors.MidnightBlue,
                                            color: CustomColors.MidnightBlue
                                        }
                                    }}
                                />
                            ))}
                        </Box>
                    </Box>
                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {error}
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {results && (
                <Box>
                    <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
                        <Typography variant="h6" gutterBottom>
                            <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Research Results Summary
                        </Typography>
                        <Stack direction="row" spacing={3}>
                            <Box>
                                <Typography variant="h4" color="primary" fontWeight={FontWeight.Bold}>
                                    {results.steps?.search?.results?.length || 0}
                                </Typography>
                                <Typography variant="caption">URLs Found</Typography>
                            </Box>
                            <Box>
                                <Typography variant="h4" color="success.main" fontWeight={FontWeight.Bold}>
                                    {Object.values(processedResults).filter(data => data.scrape?.success && !data.error).length}
                                </Typography>
                                <Typography variant="caption">Sources Analyzed</Typography>
                            </Box>
                            <Box>
                                <Typography variant="h4" color="secondary.main" fontWeight={FontWeight.Bold}>
                                    {synthesisResult ? 1 : 0}
                                </Typography>
                                <Typography variant="caption">Content Briefs Generated</Typography>
                            </Box>
                        </Stack>
                    </Paper>

                    {renderSynthesisResult()}
                    {renderSearchResults()}
                    {renderAnalysis()}
                </Box>
            )}
        </Box>
    );
};

export default ContentFinder;