export interface ArticleAnalysis {
    overview: string;
    key_insights: string[];
    outstaffer_opportunity: string;
}

export interface MultiArticleAnalysis extends ArticleAnalysis {
    cross_article_themes: string[];
}
