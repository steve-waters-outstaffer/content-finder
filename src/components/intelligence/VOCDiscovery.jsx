// src/components/intelligence/VOCDiscovery.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControlLabel,
    Grid,
    Stack,
    TextField,
    Typography,
    MenuItem,
    Paper,
    Link,
} from '@mui/material';
import InsightsIcon from '@mui/icons-material/Insights';
import ForumIcon from '@mui/icons-material/Forum';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { CustomColors, FontWeight } from '../../theme';

const DEFAULT_API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app';
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || DEFAULT_API_BASE;

const defaultSegments = ['SMB Leaders'];

const PostCard = ({ post, isGreyedOut, onToggle, isSelected, showAnalysis }) => (
    <Card
        variant="outlined"
        sx={{
            mb: 2,
            opacity: isGreyedOut ? 0.5 : 1,
            transition: 'opacity 0.3s',
        }}
    >
        <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                {onToggle && (
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={Boolean(isSelected)}
                                onChange={() => onToggle(post.id)}
                            />
                        }
                        label=""
                        sx={{ mr: 1, mt: -1 }}
                    />
                )}
                <Box flexGrow={1}>
                    <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                        {post.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        r/{post.subreddit} • Score {post.score} • {post.num_comments} comments
                    </Typography>
                    {post.content_snippet && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            {post.content_snippet}
                        </Typography>
                    )}
                    {showAnalysis && post.ai_analysis && (
                        <Box sx={{ mt: 2, p: 2, bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}>
                            <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                AI Insight
                            </Typography>
                            <Typography variant="body2">
                                <strong>Relevance:</strong> {post.ai_analysis.relevance_score ?? 'n/a'}
                            </Typography>
                            {post.ai_analysis.identified_pain_point && (
                                <Typography variant="body2" sx={{ mt: 0.5 }}>
                                    <strong>Pain Point:</strong> {post.ai_analysis.identified_pain_point}
                                </Typography>
                            )}
                            {post.ai_analysis.reasoning && (
                                <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                                    {post.ai_analysis.reasoning}
                                </Typography>
                            )}
                        </Box>
                    )}
                    {post.url && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                            <Link href={post.url} target="_blank" rel="noreferrer">
                                View discussion
                            </Link>
                        </Typography>
                    )}
                </Box>
            </Stack>
        </CardContent>
    </Card>
);


const VOCDiscovery = () => {
    const [segmentName, setSegmentName] = useState(defaultSegments[0]);
    const [availableSegments, setAvailableSegments] = useState(defaultSegments);
    const [error, setError] = useState('');
    const [warnings, setWarnings] = useState([]);
    const [rawPosts, setRawPosts] = useState([]);
    const [filteredPosts, setFilteredPosts] = useState([]);
    const [analyzedPosts, setAnalyzedPosts] = useState([]);
    const [googleTrends, setGoogleTrends] = useState([]);
    const [curatedQueries, setCuratedQueries] = useState([]);
    const [feedMessage, setFeedMessage] = useState('');
    const [isDiscoveryStarted, setIsDiscoveryStarted] = useState(false);
    const [discoveryLogs, setDiscoveryLogs] = useState([]);
    const [segmentConfig, setSegmentConfig] = useState(null);
    const [discoveryResults, setDiscoveryResults] = useState(null);

    const selectedPosts = useMemo(() => new Set(analyzedPosts.filter(p => p.selected).map(p => p.id)), [analyzedPosts]);

    const startDiscovery = useCallback(async () => {
        if (!segmentName) {
            return;
        }

        setIsDiscoveryStarted(true);
        setError('');
        setWarnings([]);
        setFeedMessage('');
        setRawPosts([]);
        setFilteredPosts([]);
        setAnalyzedPosts([]);
        setGoogleTrends([]);
        setCuratedQueries([]);
        setDiscoveryLogs(['Starting VOC Discovery...']);
        setDiscoveryResults(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    segment_name: segmentName,
                    enable_reddit: true,
                    enable_trends: true,
                    enable_curated_queries: true,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            setRawPosts(data.raw_reddit_posts || []);
            setFilteredPosts(data.filtered_reddit_posts || []);
            const posts = (data.reddit_posts || []).map((post) => ({
                ...post,
                selected: post.selected !== false,
            }));
            setAnalyzedPosts(posts);

            setGoogleTrends(data.google_trends || []);
            setCuratedQueries(data.curated_queries || []);
            setWarnings(data.warnings || []);
            setDiscoveryResults(data);

            const formattedLogs = Array.isArray(data.logs)
                ? data.logs.map((log) => `[${(log.level || 'info').toUpperCase()}] ${log.message}`)
                : [];
            setDiscoveryLogs(formattedLogs.length ? formattedLogs : ['VOC Discovery completed.']);
        } catch (error) {
            console.error('Discovery failed:', error);
            setError('Unable to load trend discovery data. Please try again.');
            setDiscoveryLogs((prevLogs) => [...prevLogs, `Error: ${error.message}`]);
        } finally {
            setIsDiscoveryStarted(false);
        }
    }, [segmentName]);

    useEffect(() => {
        const loadSegments = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/intelligence/config`);
                if (!response.ok) {
                    return;
                }
                const config = await response.json();
                const segments =
                    config?.monthly_run?.segments?.map((segment) => segment.name).filter(Boolean) || [];

                if (segments.length) {
                    setAvailableSegments(segments);
                    if (!segments.includes(segmentName)) {
                        setSegmentName(segments[0]);
                        return;
                    }
                }
            } catch (configError) {
                console.warn('Unable to load intelligence segments:', configError);
            }
        };

        loadSegments();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        setSegmentConfig(null);
        setDiscoveryResults(null);
        setRawPosts([]);
        setFilteredPosts([]);
        setAnalyzedPosts([]);
        setGoogleTrends([]);
        setCuratedQueries([]);
        setWarnings([]);
        setError('');
        setFeedMessage('');
        setDiscoveryLogs([]);
        setIsDiscoveryStarted(false);

        if (!segmentName) {
            return;
        }

        let isCancelled = false;

        const fetchConfig = async () => {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/segment-config/${encodeURIComponent(segmentName)}`,
                );

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (!isCancelled) {
                    setSegmentConfig({
                        subreddits: Array.isArray(data.subreddits) ? data.subreddits : [],
                        trends_keywords: Array.isArray(data.trends_keywords)
                            ? data.trends_keywords
                            : [],
                    });
                }
            } catch (configError) {
                console.error('Failed to fetch segment config:', configError);
                if (!isCancelled) {
                    setSegmentConfig({ subreddits: [], trends_keywords: [] });
                }
            }
        };

        fetchConfig();

        return () => {
            isCancelled = true;
        };
    }, [segmentName]);

    const handleSegmentChange = (event) => {
        setSegmentName(event.target.value);
    };

    const handleTogglePost = (postId) => {
        setAnalyzedPosts((prevPosts) =>
            prevPosts.map((post) =>
                post.id === postId
                    ? {
                        ...post,
                        selected: !post.selected,
                    }
                    : post,
            ),
        );
    };

    const handleFeed = () => {
        const selectedCount = selectedPosts.size;
        if (!selectedCount) {
            setFeedMessage('Select at least one Reddit insight to feed into the Intelligence Engine.');
            return;
        }

        setFeedMessage(
            `Prepared ${selectedCount} Reddit insight${selectedCount > 1 ? 's' : ''} for the Intelligence Engine.`,
        );
    };

    const filteredPostIds = useMemo(() => new Set(filteredPosts.map(p => p.id)), [filteredPosts]);


    return (
        <Box>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'flex-end' }} mb={3}>
                <TextField
                    select
                    label="Audience Segment"
                    value={segmentName}
                    onChange={handleSegmentChange}
                    sx={{ minWidth: 220 }}
                    size="small"
                >
                    {availableSegments.map((segment) => (
                        <MenuItem key={segment} value={segment}>
                            {segment}
                        </MenuItem>
                    ))}
                </TextField>

                <Button
                    variant="contained"
                    color="primary"
                    onClick={startDiscovery}
                    disabled={isDiscoveryStarted || !segmentName}
                >
                    {isDiscoveryStarted ? 'Discovery Running...' : 'Start Discovery'}
                </Button>

                <Stack direction="row" spacing={1} alignItems="center" color={CustomColors.UIGrey600}>
                    <InsightsIcon fontSize="small" />
                    <Typography variant="body2">Automatically surfaces Reddit & Google Trends insights.</Typography>
                </Stack>
            </Stack>

            {!isDiscoveryStarted && segmentConfig && (
                <Card sx={{ mt: 2 }}>
                    <CardContent>
                        <Typography variant="h6" fontWeight={FontWeight.SemiBold} gutterBottom>
                            🔍 Discovery Configuration
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    Subreddits to Search
                                </Typography>
                                {segmentConfig.subreddits?.length ? (
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                        {segmentConfig.subreddits.map((subreddit) => (
                                            <Chip key={subreddit} label={`r/${subreddit}`} size="small" />
                                        ))}
                                    </Stack>
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        No subreddits configured for this segment.
                                    </Typography>
                                )}
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    Google Trends Keywords
                                </Typography>
                                {segmentConfig.trends_keywords?.length ? (
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                        {segmentConfig.trends_keywords.map((keyword) => (
                                            <Chip key={keyword} label={keyword} size="small" />
                                        ))}
                                    </Stack>
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        No Google Trends keywords configured for this segment.
                                    </Typography>
                                )}
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}

            {isDiscoveryStarted && (
                <Box
                    sx={(theme) => ({
                        mt: 2,
                        p: 2,
                        borderRadius: 2,
                        backgroundColor:
                            theme.palette.mode === 'dark'
                                ? theme.palette.grey[900]
                                : theme.palette.grey[100],
                        boxShadow: 1,
                    })}
                >
                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                        Discovery Log
                    </Typography>
                    <Box component="pre" sx={{ fontSize: 12, whiteSpace: 'pre-wrap', m: 0, maxHeight: 300, overflowY: 'auto' }}>
                        {discoveryLogs.join('\n')}
                    </Box>
                </Box>
            )}

            {isDiscoveryStarted && (
                <Box display="flex" justifyContent="center" my={4}>
                    <CircularProgress />
                </Box>
            )}

            {!isDiscoveryStarted && discoveryResults && (
                <>
                    <Alert severity="success" sx={{ my: 2 }}>
                        Discovery completed with {discoveryResults.raw_reddit_posts?.length || 0} posts found, {discoveryResults.filtered_reddit_posts?.length || 0} passed filters, and {discoveryResults.reddit_posts?.length || 0} analyzed.
                    </Alert>

                    <Grid container spacing={3}>
                        {/* Column 1: Raw Reddit Feed */}
                        <Grid item xs={12} md={4}>
                            <Typography variant="h6" fontWeight={FontWeight.SemiBold} gutterBottom>
                                Raw Feed ({rawPosts.length})
                            </Typography>
                            <Paper sx={{ p: 2, height: '70vh', overflowY: 'auto', bgcolor: 'grey.50' }}>
                                {rawPosts.map(post => (
                                    <PostCard
                                        key={`raw-${post.id}`}
                                        post={post}
                                        isGreyedOut={!filteredPostIds.has(post.id)}
                                    />
                                ))}
                            </Paper>
                        </Grid>

                        {/* Column 2: Passed Initial Filters */}
                        <Grid item xs={12} md={4}>
                            <Typography variant="h6" fontWeight={FontWeight.SemiBold} gutterBottom>
                                Passed Filters ({filteredPosts.length})
                            </Typography>
                            <Paper sx={{ p: 2, height: '70vh', overflowY: 'auto', bgcolor: 'grey.50' }}>
                                {filteredPosts.map(post => (
                                    <PostCard key={`filtered-${post.id}`} post={post} />
                                ))}
                            </Paper>
                        </Grid>

                        {/* Column 3: AI Analysis & Verdict */}
                        <Grid item xs={12} md={4}>
                            <Typography variant="h6" fontWeight={FontWeight.SemiBold} gutterBottom>
                                AI Analysis ({analyzedPosts.length})
                            </Typography>
                            <Paper sx={{ p: 2, height: '70vh', overflowY: 'auto', bgcolor: 'grey.50' }}>
                                {analyzedPosts.map(post => (
                                    <PostCard
                                        key={`analyzed-${post.id}`}
                                        post={post}
                                        onToggle={handleTogglePost}
                                        isSelected={selectedPosts.has(post.id)}
                                        showAnalysis
                                    />
                                ))}
                            </Paper>
                        </Grid>
                    </Grid>

                    <Divider sx={{ my: 4 }} />

                    <Grid container spacing={3}>
                        <Grid item xs={12} md={6}>
                            <Card sx={{ height: '100%' }}>
                                <CardContent>
                                    <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                        <TrendingUpIcon color="primary" />
                                        <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                                            Google Trends Signals
                                        </Typography>
                                    </Stack>

                                    {!googleTrends.length && !isDiscoveryStarted ? (
                                        <Typography variant="body2" color="text.secondary">
                                            Google Trends data is unavailable for this segment.
                                        </Typography>
                                    ) : (
                                        <Stack spacing={2}>
                                            {googleTrends.map((trend) => (
                                                <Box key={trend.query} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                                                    <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                                        {trend.query}
                                                    </Typography>
                                                    {trend.comparison_keyword && (
                                                        <Typography variant="caption" color="text.secondary">
                                                            Compared against {trend.comparison_keyword}
                                                        </Typography>
                                                    )}
                                                    <Divider sx={{ my: 1 }} />
                                                    <Typography variant="body2" color="text.secondary">
                                                        {trend.interest_over_time?.length || 0} recent data points captured.
                                                    </Typography>
                                                    {trend.related_queries?.rising?.length ? (
                                                        <Box sx={{ mt: 1 }}>
                                                            <Typography variant="subtitle2" gutterBottom>
                                                                Rising searches
                                                            </Typography>
                                                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                                {trend.related_queries.rising.slice(0, 5).map((item, index) => (
                                                                    <Chip key={`${trend.query}-rising-${index}`} label={item.query || item.topic_title || 'Insight'} size="small" />
                                                                ))}
                                                            </Stack>
                                                        </Box>
                                                    ) : null}
                                                </Box>
                                            ))}
                                        </Stack>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                        <Grid item xs={12} md={6}>
                            <Card sx={{ flexGrow: 1 }}>
                                <CardContent>
                                    <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                        <TaskAltIcon color="success" />
                                        <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                                            Curated Research Prompts
                                        </Typography>
                                    </Stack>

                                    {!curatedQueries.length && !isDiscoveryStarted ? (
                                        <Typography variant="body2" color="text.secondary">
                                            Curated queries will appear once AI analysis is available.
                                        </Typography>
                                    ) : !curatedQueries.length && isDiscoveryStarted ? (
                                        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                            No actionable insights identified this time. Check back after new discussions emerge in your target communities.
                                        </Typography>
                                    ) : (
                                        <Stack spacing={1}>
                                            {curatedQueries.map((query, index) => (
                                                <Chip key={index} label={query} variant="outlined" />
                                            ))}
                                        </Stack>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>
                </>
            )}

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}

            {warnings.map((warning, index) => (
                <Alert key={index} severity="warning" sx={{ mb: 2 }}>
                    {warning}
                </Alert>
            ))}

            <Divider sx={{ my: 4 }} />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
                <Button
                    variant="contained"
                    color="secondary"
                    onClick={handleFeed}
                    disabled={!selectedPosts.size}
                >
                    Feed to Intelligence Engine
                </Button>
                {feedMessage && (
                    <Typography variant="body2" color="text.secondary">
                        {feedMessage}
                    </Typography>
                )}
            </Stack>
        </Box>
    );
};

export default VOCDiscovery;