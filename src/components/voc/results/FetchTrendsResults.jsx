import React from 'react';
import { Chip, Stack, Typography, Box, Alert, Divider } from '@mui/material';
import { FontWeight } from '../../../theme';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';

const FetchTrendsResults = ({ stepInfo }) => {
    const trends = stepInfo?.data || [];
    const warnings = stepInfo?.warnings || [];

    const hasRelatedData = (trend) => {
        const hasQueries = (trend.related_queries?.top?.length > 0 || trend.related_queries?.rising?.length > 0);
        const hasTopics = (trend.related_topics?.top?.length > 0 || trend.related_topics?.rising?.length > 0);
        return hasQueries || hasTopics;
    };

    return (
        <Stack spacing={3}>
            <Box>
                <Typography variant="h6" fontWeight={FontWeight.Medium}>
                    Google Trends ({trends.length} keywords)
                </Typography>
                {warnings.length > 0 && (
                    <Alert severity="warning" sx={{ mt: 1 }}>
                        {warnings.join('; ')}
                    </Alert>
                )}
            </Box>

            <Stack spacing={3}>
                {trends.map((trend, idx) => (
                    <Box key={trend.query || idx} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1, maxWidth: '100%', overflow: 'hidden' }}>
                        <Stack spacing={2}>
                            {/* Keyword Header */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ShowChartIcon color="primary" />
                                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                    {trend.query}
                                </Typography>
                                <Chip 
                                    label={`${trend.interest_over_time?.length || 0} data points`} 
                                    size="small" 
                                    variant="outlined"
                                />
                            </Box>

                            {/* Interest Over Time */}
                            {trend.interest_over_time && trend.interest_over_time.length > 0 ? (
                                <Box sx={{ maxWidth: '100%' }}>
                                    <Typography variant="body2" color="text.secondary" gutterBottom>
                                        Interest over time data available
                                    </Typography>
                                </Box>
                            ) : (
                                <Alert severity="info" sx={{ py: 0.5, maxWidth: '100%' }}>
                                    No interest over time data available
                                </Alert>
                            )}

                            <Divider />

                            {/* Related Queries */}
                            {trend.related_queries && (trend.related_queries.top?.length > 0 || trend.related_queries.rising?.length > 0) ? (
                                <Box sx={{ width: '100%' }}>
                                    <Typography variant="body2" fontWeight={FontWeight.Medium} gutterBottom>
                                        Related Queries
                                    </Typography>
                                    <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 1 }}>
                                        {trend.related_queries.top?.length > 0 && (
                                            <Box sx={{ minWidth: 0, flex: '1 1 45%' }}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Top ({trend.related_queries.top.length})
                                                </Typography>
                                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                                                    {trend.related_queries.top.slice(0, 5).map((q, i) => (
                                                        <Chip key={i} label={q.query} size="small" sx={{ maxWidth: '100%' }} />
                                                    ))}
                                                </Stack>
                                            </Box>
                                        )}
                                        {trend.related_queries.rising?.length > 0 && (
                                            <Box sx={{ minWidth: 0, flex: '1 1 45%' }}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Rising ({trend.related_queries.rising.length})
                                                </Typography>
                                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                                                    {trend.related_queries.rising.slice(0, 5).map((q, i) => (
                                                        <Chip 
                                                            key={i} 
                                                            label={q.query} 
                                                            size="small" 
                                                            color="primary"
                                                            icon={<TrendingUpIcon />}
                                                            sx={{ maxWidth: '100%' }}
                                                        />
                                                    ))}
                                                </Stack>
                                            </Box>
                                        )}
                                    </Stack>
                                </Box>
                            ) : (
                                <Alert severity="info" sx={{ py: 0.5, maxWidth: '100%' }}>
                                    No related queries available for this keyword
                                </Alert>
                            )}

                            {/* Related Topics */}
                            {trend.related_topics && (trend.related_topics.top?.length > 0 || trend.related_topics.rising?.length > 0) ? (
                                <Box sx={{ width: '100%' }}>
                                    <Typography variant="body2" fontWeight={FontWeight.Medium} gutterBottom>
                                        Related Topics
                                    </Typography>
                                    <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 1 }}>
                                        {trend.related_topics.top?.length > 0 && (
                                            <Box sx={{ minWidth: 0, flex: '1 1 45%' }}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Top ({trend.related_topics.top.length})
                                                </Typography>
                                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                                                    {trend.related_topics.top.slice(0, 5).map((t, i) => (
                                                        <Chip key={i} label={t.topic_title || t.formattedValue} size="small" variant="outlined" sx={{ maxWidth: '100%' }} />
                                                    ))}
                                                </Stack>
                                            </Box>
                                        )}
                                        {trend.related_topics.rising?.length > 0 && (
                                            <Box sx={{ minWidth: 0, flex: '1 1 45%' }}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Rising ({trend.related_topics.rising.length})
                                                </Typography>
                                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                                                    {trend.related_topics.rising.slice(0, 5).map((t, i) => (
                                                        <Chip 
                                                            key={i} 
                                                            label={t.topic_title || t.formattedValue} 
                                                            size="small" 
                                                            variant="outlined"
                                                            color="primary"
                                                            sx={{ maxWidth: '100%' }}
                                                        />
                                                    ))}
                                                </Stack>
                                            </Box>
                                        )}
                                    </Stack>
                                </Box>
                            ) : (
                                <Alert severity="info" sx={{ py: 0.5, maxWidth: '100%' }}>
                                    No related topics available for this keyword
                                </Alert>
                            )}

                            {/* Overall status */}
                            {!hasRelatedData(trend) && trend.interest_over_time?.length > 0 && (
                                <Alert severity="success" sx={{ py: 0.5, maxWidth: '100%' }}>
                                    Successfully fetched interest data, but no related trends available for this niche keyword
                                </Alert>
                            )}
                        </Stack>
                    </Box>
                ))}
            </Stack>
        </Stack>
    );
};

export default FetchTrendsResults;
